"""
Candidate Notes API endpoints for HR tracking
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.db.models import CandidateDB, CandidateNoteDB, UserDB

router = APIRouter(prefix="/api/candidates", tags=["notes"])


# Pydantic schemas
class NoteCreate(BaseModel):
    content: str
    note_type: str = "general"  # general, interview, feedback, status_change
    rating: Optional[int] = None
    new_status: Optional[str] = None


class NoteResponse(BaseModel):
    id: str
    candidate_id: str
    note_type: str
    content: str
    rating: Optional[int]
    previous_status: Optional[str]
    new_status: Optional[str]
    created_at: datetime
    user_name: Optional[str] = None

    class Config:
        from_attributes = True


class NotesListResponse(BaseModel):
    items: List[NoteResponse]
    total: int


@router.get("/{candidate_id}/notes", response_model=NotesListResponse)
async def get_candidate_notes(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get all notes for a candidate."""
    # Verify candidate exists
    result = await db.execute(
        select(CandidateDB).where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Get notes with user info
    result = await db.execute(
        select(CandidateNoteDB)
        .options(selectinload(CandidateNoteDB.user))
        .where(CandidateNoteDB.candidate_id == candidate_id)
        .order_by(CandidateNoteDB.created_at.desc())
    )
    notes = result.scalars().all()
    
    return NotesListResponse(
        items=[
            NoteResponse(
                id=str(n.id),
                candidate_id=str(n.candidate_id),
                note_type=n.note_type,
                content=n.content,
                rating=n.rating,
                previous_status=n.previous_status,
                new_status=n.new_status,
                created_at=n.created_at,
                user_name=n.user.full_name if n.user else None
            )
            for n in notes
        ],
        total=len(notes)
    )


@router.post("/{candidate_id}/notes", response_model=NoteResponse)
async def create_candidate_note(
    candidate_id: UUID,
    note: NoteCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new note for a candidate."""
    # Verify candidate exists and get current status
    result = await db.execute(
        select(CandidateDB).where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    previous_status = candidate.status
    
    # Create note
    db_note = CandidateNoteDB(
        candidate_id=candidate_id,
        note_type=note.note_type,
        content=note.content,
        rating=note.rating,
        previous_status=previous_status if note.new_status else None,
        new_status=note.new_status
    )
    db.add(db_note)
    
    # Update candidate status if changing
    if note.new_status and note.new_status != candidate.status:
        candidate.status = note.new_status
    
    # Update candidate rating if provided
    if note.rating:
        candidate.rating = note.rating
    
    await db.commit()
    await db.refresh(db_note)
    
    return NoteResponse(
        id=str(db_note.id),
        candidate_id=str(db_note.candidate_id),
        note_type=db_note.note_type,
        content=db_note.content,
        rating=db_note.rating,
        previous_status=db_note.previous_status,
        new_status=db_note.new_status,
        created_at=db_note.created_at,
        user_name=None
    )


@router.patch("/{candidate_id}/rating")
async def update_candidate_rating(
    candidate_id: UUID,
    rating: int,
    db: AsyncSession = Depends(get_db)
):
    """Update candidate rating (1-5 stars)."""
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    
    result = await db.execute(
        select(CandidateDB).where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    candidate.rating = rating
    await db.commit()
    
    return {"success": True, "rating": rating}


# ============ Interview Questions Generator ============

from app.db.models import JobProfileDB
from app.adapters.llm_engine import LLMEngine


class InterviewQuestionsRequest(BaseModel):
    job_id: UUID


class InterviewQuestion(BaseModel):
    category: str
    question: str


class InterviewQuestionsResponse(BaseModel):
    candidate_name: str
    job_title: str
    skill_gaps: List[str]
    matching_skills: List[str]
    questions: dict
    generated_by_ai: bool


@router.get("/{candidate_id}/interview-questions")
async def get_interview_questions(
    candidate_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate tailored interview questions for a candidate based on a specific job.
    Analyzes skill gaps and generates questions in categories:
    - Technical questions
    - Gap questions (focused on missing skills)
    - Behavioral questions
    - Situational questions
    """
    # Get candidate
    result = await db.execute(
        select(CandidateDB).where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Get job
    result = await db.execute(
        select(JobProfileDB).where(JobProfileDB.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Calculate skill gaps
    candidate_skills = set(s.lower() for s in (candidate.skills or []))
    job_required = set(s.lower() for s in (job.required_skills or []))
    job_preferred = set(s.lower() for s in (job.preferred_skills or []))
    
    # Calculate matching and missing skills
    matching_skills = list(job_required.intersection(candidate_skills))
    skill_gaps = list(job_required - candidate_skills)
    
    # Generate questions using LLM
    llm = LLMEngine()
    questions_data = await llm.generate_interview_questions(
        candidate_name=candidate.full_name,
        candidate_skills=candidate.skills or [],
        job_title=job.title,
        job_required_skills=job.required_skills or [],
        job_preferred_skills=job.preferred_skills or [],
        skill_gaps=skill_gaps,
        matching_skills=matching_skills
    )
    
    return questions_data

