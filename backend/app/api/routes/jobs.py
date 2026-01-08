"""
Job Profile Management API Routes with PostgreSQL persistence
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import DocumentParser, EmbeddingService, LLMEngine
from app.core.database import get_db
from app.db.models import JobProfileDB
from app.domain import EducationLevel, JobStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Job Profiles"])


# ============ Request/Response Schemas ============

class CreateJobRequest(BaseModel):
    title: str
    department: Optional[str] = None
    description: Optional[str] = None
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    min_experience_years: int = 0
    education_level: Optional[str] = None
    status: Optional[str] = "active"


class JobProfileResponse(BaseModel):
    id: UUID
    title: str
    department: Optional[str]
    description: Optional[str]
    required_skills: List[str]
    preferred_skills: List[str]
    min_experience_years: int
    education_level: Optional[str]
    status: str
    
    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    items: List[JobProfileResponse]
    total: int


class ExtractedSkillsResponse(BaseModel):
    title: str
    required_skills: List[str]
    preferred_skills: List[str]
    min_experience_years: int
    education_level: Optional[str]
    raw_description: str


# ============ Dependencies ============

def get_document_parser() -> DocumentParser:
    return DocumentParser()


def get_llm_engine() -> LLMEngine:
    return LLMEngine()


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


# ============ Endpoints ============

@router.post("", response_model=JobProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_job_profile(
    request: CreateJobRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new job profile and save to PostgreSQL."""
    job_db = JobProfileDB(
        title=request.title,
        department=request.department,
        description=request.description,
        required_skills=request.required_skills or [],
        preferred_skills=request.preferred_skills or [],
        min_experience_years=request.min_experience_years,
        education_level=request.education_level,
        status=request.status or "active",
    )
    
    db.add(job_db)
    await db.commit()
    await db.refresh(job_db)
    
    return JobProfileResponse(
        id=job_db.id,
        title=job_db.title,
        department=job_db.department,
        description=job_db.description,
        required_skills=job_db.required_skills or [],
        preferred_skills=job_db.preferred_skills or [],
        min_experience_years=job_db.min_experience_years,
        education_level=job_db.education_level,
        status=job_db.status,
    )


@router.post("/analyze", response_model=ExtractedSkillsResponse)
async def analyze_job_description(
    file: UploadFile = File(None),
    description_text: Optional[str] = None,
    parser: DocumentParser = Depends(get_document_parser),
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
            required_skills=extracted.required_skills,
            preferred_skills=extracted.preferred_skills,
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
    query = select(JobProfileDB)
    
    if status_filter:
        query = query.where(JobProfileDB.status == status_filter)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return JobListResponse(
        items=[
            JobProfileResponse(
                id=j.id,
                title=j.title,
                department=j.department,
                description=j.description,
                required_skills=j.required_skills or [],
                preferred_skills=j.preferred_skills or [],
                min_experience_years=j.min_experience_years,
                education_level=j.education_level,
                status=j.status,
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
    
    return JobProfileResponse(
        id=job.id,
        title=job.title,
        department=job.department,
        description=job.description,
        required_skills=job.required_skills or [],
        preferred_skills=job.preferred_skills or [],
        min_experience_years=job.min_experience_years,
        education_level=job.education_level,
        status=job.status,
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
    
    job.title = request.title
    job.department = request.department
    job.description = request.description
    job.required_skills = request.required_skills or []
    job.preferred_skills = request.preferred_skills or []
    job.min_experience_years = request.min_experience_years
    job.education_level = request.education_level
    
    await db.commit()
    await db.refresh(job)
    
    return JobProfileResponse(
        id=job.id,
        title=job.title,
        department=job.department,
        description=job.description,
        required_skills=job.required_skills or [],
        preferred_skills=job.preferred_skills or [],
        min_experience_years=job.min_experience_years,
        education_level=job.education_level,
        status=job.status,
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a job profile from PostgreSQL."""
    result = await db.execute(
        select(JobProfileDB).where(JobProfileDB.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job profile not found"
        )
    
    await db.delete(job)
    await db.commit()


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
