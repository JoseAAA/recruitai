"""
Job Profile Management API Routes with PostgreSQL persistence
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import DocumentExtractor, EmbeddingService, LLMEngine
from app.core.database import get_db
from app.db.models import CandidateDB, JobProfileDB
from app.domain import DEFAULT_SCORING_CONFIG, EducationLevel, JobStatus, ScoringDimension

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Job Profiles"])


# ============ Request/Response Schemas ============

class ScoringDimensionSchema(BaseModel):
    dimension: str
    weight: float = Field(ge=0, le=1)
    description: Optional[str] = None


class CreateJobRequest(BaseModel):
    title: str
    department: Optional[str] = None
    description: Optional[str] = None
    seniority_level: Optional[str] = None
    work_modality: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    key_objectives: List[str] = Field(default_factory=list)
    min_experience_years: int = 0
    education_level: Optional[str] = None
    status: Optional[str] = "active"
    scoring_config: Optional[List[ScoringDimensionSchema]] = Field(
        default=None,
        description="Custom scoring weights per dimension. Null = use global defaults."
    )


class JobProfileResponse(BaseModel):
    id: UUID
    title: str
    department: Optional[str]
    description: Optional[str]
    seniority_level: Optional[str] = None
    work_modality: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    required_skills: List[str]
    preferred_skills: List[str]
    responsibilities: List[str] = Field(default_factory=list)
    key_objectives: List[str] = Field(default_factory=list)
    min_experience_years: int
    education_level: Optional[str]
    status: str
    scoring_config: Optional[List[dict]] = None
    candidate_count: int = 0

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    items: List[JobProfileResponse]
    total: int


class ExtractedSkillsResponse(BaseModel):
    title: str
    department: Optional[str] = None
    description: Optional[str] = None
    seniority_level: Optional[str] = None
    work_modality: Optional[str] = None
    industry: Optional[str] = None
    required_skills: List[str]
    preferred_skills: List[str]
    responsibilities: List[str] = Field(default_factory=list)
    key_objectives: List[str] = Field(default_factory=list)
    min_experience_years: int
    education_level: Optional[str]
    raw_description: str


# ============ Dependencies ============

def get_document_parser() -> DocumentExtractor:
    return DocumentExtractor()


def get_llm_engine() -> LLMEngine:
    return LLMEngine()


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


# ============ Endpoints ============

def _validate_scoring_config(scoring_config: Optional[List[ScoringDimensionSchema]]) -> Optional[List[dict]]:
    """Validate that scoring weights sum to 1.0 and return as list of dicts."""
    if not scoring_config:
        return None
    total = sum(d.weight for d in scoring_config)
    if abs(total - 1.0) > 0.01:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Los pesos de scoring deben sumar 1.0, obtenido: {total:.2f}"
        )
    return [d.model_dump() for d in scoring_config]


@router.get("/scoring-presets")
async def get_scoring_presets():
    """Return the default scoring configuration preset."""
    return {
        "default": [d.model_dump() for d in DEFAULT_SCORING_CONFIG]
    }


@router.post("", response_model=JobProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_job_profile(
    request: CreateJobRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new job profile and save to PostgreSQL."""
    scoring_config = _validate_scoring_config(request.scoring_config)

    job_db = JobProfileDB(
        title=request.title,
        department=request.department,
        description=request.description,
        seniority_level=request.seniority_level,
        work_modality=request.work_modality,
        industry=request.industry,
        location=request.location,
        required_skills=request.required_skills or [],
        preferred_skills=request.preferred_skills or [],
        responsibilities=request.responsibilities or [],
        key_objectives=request.key_objectives or [],
        min_experience_years=request.min_experience_years,
        education_level=request.education_level,
        status=request.status or "active",
        scoring_config=scoring_config,
    )

    db.add(job_db)
    await db.commit()
    await db.refresh(job_db)

    # Count associated candidates
    count_result = await db.execute(
        select(CandidateDB.id).where(CandidateDB.job_id == job_db.id)
    )
    candidate_count = len(count_result.all())

    return JobProfileResponse(
        id=job_db.id,
        title=job_db.title,
        department=job_db.department,
        description=job_db.description,
        required_skills=job_db.required_skills or [],
        preferred_skills=job_db.preferred_skills or [],
        responsibilities=job_db.responsibilities or [],
        key_objectives=job_db.key_objectives or [],
        seniority_level=job_db.seniority_level,
        work_modality=job_db.work_modality,
        industry=job_db.industry,
        location=job_db.location,
        min_experience_years=job_db.min_experience_years,
        education_level=job_db.education_level,
        status=job_db.status,
        scoring_config=job_db.scoring_config,
        candidate_count=candidate_count,
    )


@router.post("/analyze", response_model=ExtractedSkillsResponse)
async def analyze_job_description(
    file: UploadFile = File(None),
    description_text: Optional[str] = Form(None),
    parser: DocumentExtractor = Depends(get_document_parser),
    llm: LLMEngine = Depends(get_llm_engine),
):
    """
    Analyze a job description and extract structured requirements.
    
    Accepts either a file upload or raw text.
    Returns extracted skills and requirements for human review (Human-in-the-loop).
    """
    if not file and not description_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a file or description_text"
        )
    
    text = description_text
    
    if file:
        content = await file.read()
        text, _ = await parser.parse_bytes(content, file.filename or "job.txt")
    
    try:
        # Extract using LLM
        extracted = await llm.extract_job_profile(text)
        
        return ExtractedSkillsResponse(
            title=extracted.title,
            department=extracted.department,
            description=extracted.description,
            seniority_level=extracted.seniority_level,
            work_modality=extracted.work_modality,
            industry=extracted.industry,
            required_skills=extracted.required_skills,
            preferred_skills=extracted.preferred_skills,
            responsibilities=extracted.responsibilities,
            key_objectives=extracted.key_objectives,
            min_experience_years=extracted.min_experience_years,
            education_level=extracted.education_level,
            raw_description=text[:2000] if text else "",
        )
        
    except Exception as e:
        logger.error(f"Failed to analyze job description: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """List all job profiles from PostgreSQL."""
    from sqlalchemy import func as sqlfunc
    query = select(JobProfileDB)

    if status_filter:
        query = query.where(JobProfileDB.status == status_filter)

    result = await db.execute(query)
    jobs = result.scalars().all()

    # Build candidate counts per job in one query
    counts_result = await db.execute(
        select(CandidateDB.job_id, sqlfunc.count(CandidateDB.id))
        .where(CandidateDB.job_id.in_([j.id for j in jobs]))
        .group_by(CandidateDB.job_id)
    )
    counts_map = {str(row[0]): row[1] for row in counts_result.all()}

    return JobListResponse(
        items=[
            JobProfileResponse(
                id=j.id,
                title=j.title,
                department=j.department,
                description=j.description,
                required_skills=j.required_skills or [],
                preferred_skills=j.preferred_skills or [],
                responsibilities=j.responsibilities or [],
                key_objectives=j.key_objectives or [],
                seniority_level=j.seniority_level,
                work_modality=j.work_modality,
                industry=j.industry,
                location=j.location,
                min_experience_years=j.min_experience_years,
                education_level=j.education_level,
                status=j.status,
                scoring_config=j.scoring_config,
                candidate_count=counts_map.get(str(j.id), 0),
            )
            for j in jobs
        ],
        total=len(jobs),
    )


@router.get("/{job_id}", response_model=JobProfileResponse)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a job profile by ID from PostgreSQL."""
    result = await db.execute(
        select(JobProfileDB).where(JobProfileDB.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job profile not found"
        )
    
    count_result = await db.execute(
        select(CandidateDB.id).where(CandidateDB.job_id == job_id)
    )
    candidate_count = len(count_result.all())

    return JobProfileResponse(
        id=job.id,
        title=job.title,
        department=job.department,
        description=job.description,
        required_skills=job.required_skills or [],
        preferred_skills=job.preferred_skills or [],
        responsibilities=job.responsibilities or [],
        key_objectives=job.key_objectives or [],
        seniority_level=job.seniority_level,
        work_modality=job.work_modality,
        industry=job.industry,
        location=job.location,
        min_experience_years=job.min_experience_years,
        education_level=job.education_level,
        status=job.status,
        scoring_config=job.scoring_config,
        candidate_count=candidate_count,
    )


@router.put("/{job_id}", response_model=JobProfileResponse)
async def update_job(
    job_id: UUID,
    request: CreateJobRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a job profile in PostgreSQL."""
    result = await db.execute(
        select(JobProfileDB).where(JobProfileDB.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job profile not found"
        )
    
    scoring_config = _validate_scoring_config(request.scoring_config)

    job.title = request.title
    job.department = request.department
    job.description = request.description
    job.required_skills = request.required_skills or []
    job.preferred_skills = request.preferred_skills or []
    job.responsibilities = request.responsibilities or []
    job.key_objectives = request.key_objectives or []
    job.seniority_level = request.seniority_level
    job.work_modality = request.work_modality
    job.industry = request.industry
    job.location = request.location
    job.min_experience_years = request.min_experience_years
    job.education_level = request.education_level
    job.scoring_config = scoring_config

    await db.commit()
    await db.refresh(job)

    count_result = await db.execute(
        select(CandidateDB.id).where(CandidateDB.job_id == job_id)
    )
    candidate_count = len(count_result.all())

    return JobProfileResponse(
        id=job.id,
        title=job.title,
        department=job.department,
        description=job.description,
        required_skills=job.required_skills or [],
        preferred_skills=job.preferred_skills or [],
        responsibilities=job.responsibilities or [],
        key_objectives=job.key_objectives or [],
        seniority_level=job.seniority_level,
        work_modality=job.work_modality,
        industry=job.industry,
        location=job.location,
        min_experience_years=job.min_experience_years,
        education_level=job.education_level,
        status=job.status,
        scoring_config=job.scoring_config,
        candidate_count=candidate_count,
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a job profile and cascade-delete all its candidates (DB + Qdrant + MinIO)."""
    result = await db.execute(
        select(JobProfileDB).where(JobProfileDB.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job profile not found"
        )

    # Fetch all candidate IDs linked to this job BEFORE deleting
    candidates_result = await db.execute(
        select(CandidateDB.id).where(CandidateDB.job_id == job_id)
    )
    candidate_ids = [row[0] for row in candidates_result.all()]

    # Clean Qdrant vectors + MinIO CVs for each candidate
    if candidate_ids:
        from app.adapters.qdrant_repo import QdrantRepository
        from app.adapters.storage import StorageService
        qdrant = QdrantRepository()
        storage = StorageService()
        for cid in candidate_ids:
            try:
                await qdrant.delete_candidate(cid)
            except Exception as e:
                logger.warning(f"Could not delete Qdrant vector for {cid}: {e}")
            try:
                storage.delete_cv(str(cid))
            except Exception as e:
                logger.warning(f"Could not delete MinIO CV for {cid}: {e}")
        logger.info(f"Cleaned {len(candidate_ids)} candidates (Qdrant + MinIO) for job {job_id}")

    # Delete job — DB CASCADE removes all linked candidates rows
    await db.delete(job)
    await db.commit()
    logger.info(f"Deleted job {job_id} and {len(candidate_ids)} associated candidates")


@router.patch("/{job_id}/status")
async def update_job_status(
    job_id: UUID,
    new_status: str,
    db: AsyncSession = Depends(get_db),
):
    """Update job status in PostgreSQL."""
    result = await db.execute(
        select(JobProfileDB).where(JobProfileDB.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job profile not found"
        )
    
    job.status = new_status
    await db.commit()
    
    return {"id": job_id, "status": new_status}
