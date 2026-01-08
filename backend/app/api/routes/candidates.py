"""
Candidate Management API Routes with PostgreSQL persistence
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import DocumentParser, EmbeddingService, LLMEngine, QdrantRepository
from app.core.database import get_db
from app.db.models import CandidateDB, ExperienceEntryDB, EducationEntryDB
from app.domain import CandidateStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["Candidates"])


# ============ Request/Response Schemas ============

class CandidateResponse(BaseModel):
    id: UUID
    full_name: str
    email: Optional[str]
    summary: Optional[str]
    skills: List[str]
    total_experience_years: float
    status: str
    
    class Config:
        from_attributes = True


class CandidateDetailResponse(CandidateResponse):
    experience: List[dict]
    education: List[dict]
    raw_text: Optional[str]


class CandidateListResponse(BaseModel):
    items: List[CandidateResponse]
    total: int
    page: int
    page_size: int


class UploadResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    extracted_name: Optional[str]
    skills_count: int
    message: str


# ============ Dependencies ============

def get_document_parser() -> DocumentParser:
    return DocumentParser()


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


def get_llm_engine() -> LLMEngine:
    return LLMEngine()


def get_qdrant_repo() -> QdrantRepository:
    return QdrantRepository()


# ============ Helper Functions ============

def calculate_experience_years(experience_entries: List[ExperienceEntryDB]) -> float:
    """Calculate total years of experience."""
    total_years = 0.0
    for exp in experience_entries:
        if exp.start_date:
            end = exp.end_date or exp.start_date
            years = (end.year - exp.start_date.year) + (end.month - exp.start_date.month) / 12
            total_years += max(0, years)
    return round(total_years, 1)


# ============ Endpoints ============

@router.post("/upload", response_model=UploadResponse)
async def upload_cv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    parser: DocumentParser = Depends(get_document_parser),
    embedder: EmbeddingService = Depends(get_embedding_service),
    llm: LLMEngine = Depends(get_llm_engine),
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
):
    """
    Upload and process a CV/Resume file.
    Extracts structured data using LLM and stores in PostgreSQL.
    """
    allowed_types = [".pdf", ".docx", ".doc"]
    filename = file.filename or "unknown"
    
    if not any(filename.lower().endswith(ext) for ext in allowed_types):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {allowed_types}"
        )
    
    try:
        # Read file content
        content = await file.read()
        
        # Parse document
        text, metadata = await parser.parse_bytes(content, filename)
        
        # Extract structured data using LLM
        extracted = await llm.extract_resume(text)
        
        # Create candidate in database
        candidate_db = CandidateDB(
            full_name=extracted.full_name,
            email=extracted.email,
            phone=extracted.phone,
            summary=extracted.summary,
            skills=extracted.skills or [],
            raw_text=text,
            file_path=filename,
            file_hash=metadata.get("file_hash"),
            status="new",
        )
        
        db.add(candidate_db)
        await db.commit()
        await db.refresh(candidate_db)
        
        # Add experience entries
        for exp in extracted.experience or []:
            exp_db = ExperienceEntryDB(
                candidate_id=candidate_db.id,
                company=exp.company,
                title=exp.title,
                start_date=exp.start_date,
                end_date=exp.end_date,
                description=exp.description,
                is_current=exp.is_current if hasattr(exp, 'is_current') else False,
            )
            db.add(exp_db)
        
        # Add education entries
        for edu in extracted.education or []:
            edu_db = EducationEntryDB(
                candidate_id=candidate_db.id,
                institution=edu.institution,
                degree=edu.degree,
                field_of_study=edu.field_of_study,
                start_date=getattr(edu, 'start_date', None),
                end_date=getattr(edu, 'end_date', None),
            )
            db.add(edu_db)
        
        await db.commit()
        
        # Generate embeddings and index in Qdrant
        experience_text = " ".join([
            f"{exp.title} at {exp.company}: {exp.description or ''}"
            for exp in extracted.experience or []
        ])
        education_text = " ".join([
            f"{edu.degree} from {edu.institution}"
            for edu in extracted.education or []
        ])
        skills_text = ", ".join(extracted.skills or [])
        
        vectors = embedder.embed_candidate_aspects(
            experience_text=experience_text,
            education_text=education_text,
            skills_text=skills_text,
            summary_text=extracted.summary or ""
        )
        
        await qdrant.upsert_candidate(
            candidate_id=candidate_db.id,
            vectors=vectors,
            payload={
                "full_name": candidate_db.full_name,
                "skills": candidate_db.skills,
                "experience_years": 0,
                "status": candidate_db.status,
            }
        )
        
        return UploadResponse(
            id=candidate_db.id,
            filename=filename,
            status="processed",
            extracted_name=candidate_db.full_name,
            skills_count=len(candidate_db.skills),
            message="CV processed and indexed successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to process CV {filename}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process CV: {str(e)}"
        )


@router.get("", response_model=CandidateListResponse)
async def list_candidates(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """List all candidates with pagination from PostgreSQL."""
    # Build query
    query = select(CandidateDB)
    
    if status_filter:
        query = query.where(CandidateDB.status == status_filter)
    
    # Get total count
    count_result = await db.execute(select(CandidateDB.id))
    total = len(count_result.all())
    
    # Pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    candidates = result.scalars().all()
    
    return CandidateListResponse(
        items=[
            CandidateResponse(
                id=c.id,
                full_name=c.full_name,
                email=c.email,
                summary=c.summary,
                skills=c.skills or [],
                total_experience_years=0,  # Would need to load experience
                status=c.status,
            )
            for c in candidates
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{candidate_id}", response_model=CandidateDetailResponse)
async def get_candidate(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed candidate information from PostgreSQL."""
    result = await db.execute(
        select(CandidateDB).where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    # Load experience
    exp_result = await db.execute(
        select(ExperienceEntryDB).where(ExperienceEntryDB.candidate_id == candidate_id)
    )
    experience = exp_result.scalars().all()
    
    # Load education
    edu_result = await db.execute(
        select(EducationEntryDB).where(EducationEntryDB.candidate_id == candidate_id)
    )
    education = edu_result.scalars().all()
    
    return CandidateDetailResponse(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        summary=candidate.summary,
        skills=candidate.skills or [],
        total_experience_years=calculate_experience_years(experience),
        status=candidate.status,
        experience=[
            {
                "company": e.company,
                "title": e.title,
                "start_date": str(e.start_date) if e.start_date else None,
                "end_date": str(e.end_date) if e.end_date else None,
                "description": e.description,
            }
            for e in experience
        ],
        education=[
            {
                "institution": e.institution,
                "degree": e.degree,
                "field_of_study": e.field_of_study,
            }
            for e in education
        ],
        raw_text=candidate.raw_text,
    )


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
):
    """Delete a candidate from PostgreSQL and Qdrant."""
    result = await db.execute(
        select(CandidateDB).where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    # Remove from vector store
    await qdrant.delete_candidate(candidate_id)
    
    # Remove from database
    await db.delete(candidate)
    await db.commit()


@router.patch("/{candidate_id}/status")
async def update_candidate_status(
    candidate_id: UUID,
    new_status: str,
    db: AsyncSession = Depends(get_db),
):
    """Update candidate status in PostgreSQL."""
    result = await db.execute(
        select(CandidateDB).where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    candidate.status = new_status
    await db.commit()
    
    return {"id": candidate_id, "status": new_status}
