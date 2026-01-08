"""
Dashboard Statistics API Routes
Provides real-time metrics from PostgreSQL
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.db.models import CandidateDB, JobProfileDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["Statistics"])


# ============ Response Schemas ============

class DashboardStats(BaseModel):
    total_candidates: int
    total_jobs: int
    active_jobs: int
    new_candidates_this_week: int
    candidates_by_status: dict
    recent_candidates: List[dict]
    recent_jobs: List[dict]


class QuickStats(BaseModel):
    candidates: int
    jobs: int
    new_this_week: int


# ============ Endpoints ============

@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    Get comprehensive dashboard statistics.
    Returns real-time metrics from the database.
    """
    # Total candidates
    result = await db.execute(select(func.count(CandidateDB.id)))
    total_candidates = result.scalar() or 0
    
    # Total jobs
    result = await db.execute(select(func.count(JobProfileDB.id)))
    total_jobs = result.scalar() or 0
    
    # Active jobs
    result = await db.execute(
        select(func.count(JobProfileDB.id)).where(JobProfileDB.status == "active")
    )
    active_jobs = result.scalar() or 0
    
    # New candidates this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    result = await db.execute(
        select(func.count(CandidateDB.id)).where(CandidateDB.created_at >= week_ago)
    )
    new_this_week = result.scalar() or 0
    
    # Candidates by status
    result = await db.execute(
        select(CandidateDB.status, func.count(CandidateDB.id))
        .group_by(CandidateDB.status)
    )
    status_counts = dict(result.all())
    
    # Recent candidates (last 5)
    result = await db.execute(
        select(CandidateDB)
        .order_by(CandidateDB.created_at.desc())
        .limit(5)
    )
    recent_candidates = [
        {
            "id": str(c.id),
            "full_name": c.full_name,
            "skills_count": len(c.skills or []),
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in result.scalars().all()
    ]
    
    # Recent jobs (last 5)
    result = await db.execute(
        select(JobProfileDB)
        .order_by(JobProfileDB.created_at.desc())
        .limit(5)
    )
    recent_jobs = [
        {
            "id": str(j.id),
            "title": j.title,
            "status": j.status,
            "required_skills_count": len(j.required_skills or []),
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in result.scalars().all()
    ]
    
    return DashboardStats(
        total_candidates=total_candidates,
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        new_candidates_this_week=new_this_week,
        candidates_by_status=status_counts,
        recent_candidates=recent_candidates,
        recent_jobs=recent_jobs,
    )


@router.get("/quick", response_model=QuickStats)
async def get_quick_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get quick stats for header/navbar display."""
    # Total candidates
    result = await db.execute(select(func.count(CandidateDB.id)))
    total_candidates = result.scalar() or 0
    
    # Total jobs
    result = await db.execute(select(func.count(JobProfileDB.id)))
    total_jobs = result.scalar() or 0
    
    # New this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    result = await db.execute(
        select(func.count(CandidateDB.id)).where(CandidateDB.created_at >= week_ago)
    )
    new_this_week = result.scalar() or 0
    
    return QuickStats(
        candidates=total_candidates,
        jobs=total_jobs,
        new_this_week=new_this_week,
    )


# ============ AI-Powered Top Matches ============

class TopCandidateMatch(BaseModel):
    candidate_id: str
    candidate_name: str
    job_id: str
    job_title: str
    match_score: float
    skills_match: List[str]
    missing_skills: List[str]
    recommendation: str


class JobWithMatches(BaseModel):
    job_id: str
    job_title: str
    required_skills: List[str]
    top_candidates: List[dict]


class TopMatchesResponse(BaseModel):
    top_candidates: List[TopCandidateMatch]  # Overall top 5 to review today
    jobs_with_matches: List[JobWithMatches]  # Each job with its best matches
    star_candidates: List[TopCandidateMatch]  # >85% match alerts
    total_pending_review: int


@router.get("/top-matches", response_model=TopMatchesResponse)
async def get_top_matches(
    db: AsyncSession = Depends(get_db),
):
    """
    AI-Powered Dashboard: Get top candidate matches across all active jobs.
    
    Returns:
    - top_candidates: Top 5 overall candidates to review today
    - jobs_with_matches: Each active job with its top 3 matching candidates
    - star_candidates: Candidates with >85% match (alerts)
    - total_pending_review: Count of candidates pending review
    """
    # Get all active jobs
    result = await db.execute(
        select(JobProfileDB).where(JobProfileDB.status == "active")
    )
    active_jobs = result.scalars().all()
    
    if not active_jobs:
        return TopMatchesResponse(
            top_candidates=[],
            jobs_with_matches=[],
            star_candidates=[],
            total_pending_review=0
        )
    
    # Get all candidates
    result = await db.execute(select(CandidateDB))
    all_candidates = result.scalars().all()
    
    if not all_candidates:
        return TopMatchesResponse(
            top_candidates=[],
            jobs_with_matches=[],
            star_candidates=[],
            total_pending_review=0
        )
    
    all_matches = []
    jobs_with_matches = []
    
    # Calculate matches for each job
    for job in active_jobs:
        job_required = set(s.lower() for s in (job.required_skills or []))
        job_preferred = set(s.lower() for s in (job.preferred_skills or []))
        job_matches = []
        
        for candidate in all_candidates:
            candidate_skills = set(s.lower() for s in (candidate.skills or []))
            
            # Calculate skill match score
            if job_required:
                required_matches = job_required.intersection(candidate_skills)
                required_score = len(required_matches) / len(job_required) * 0.7
            else:
                required_score = 0.5  # Base score if no required skills
            
            if job_preferred:
                preferred_matches = job_preferred.intersection(candidate_skills)
                preferred_score = len(preferred_matches) / len(job_preferred) * 0.3
            else:
                preferred_score = 0.15
            
            total_score = required_score + preferred_score
            
            # Skills matching
            matching_skills = list(job_required.intersection(candidate_skills))
            missing = list(job_required - candidate_skills)
            
            # Generate recommendation
            if total_score >= 0.85:
                recommendation = "⭐ Candidato estrella - Revisar inmediatamente"
            elif total_score >= 0.70:
                recommendation = "👍 Buen match - Recomendado para entrevista"
            elif total_score >= 0.50:
                recommendation = "🔍 Match parcial - Revisar habilidades"
            else:
                recommendation = "📋 Match bajo - Considerar para otros puestos"
            
            match_data = TopCandidateMatch(
                candidate_id=str(candidate.id),
                candidate_name=candidate.full_name,
                job_id=str(job.id),
                job_title=job.title,
                match_score=round(total_score * 100),
                skills_match=matching_skills[:5],  # Top 5
                missing_skills=missing[:3],  # Top 3 gaps
                recommendation=recommendation
            )
            
            job_matches.append(match_data)
            all_matches.append(match_data)
        
        # Sort job matches by score
        job_matches.sort(key=lambda x: x.match_score, reverse=True)
        
        jobs_with_matches.append(JobWithMatches(
            job_id=str(job.id),
            job_title=job.title,
            required_skills=list(job_required)[:5],
            top_candidates=[
                {
                    "candidate_id": m.candidate_id,
                    "candidate_name": m.candidate_name,
                    "match_score": m.match_score,
                    "recommendation": m.recommendation
                }
                for m in job_matches[:3]  # Top 3 per job
            ]
        ))
    
    # Sort all matches globally
    all_matches.sort(key=lambda x: x.match_score, reverse=True)
    
    # Top 5 overall
    top_candidates = all_matches[:5]
    
    # Star candidates (>85%)
    star_candidates = [m for m in all_matches if m.match_score >= 85][:5]
    
    # Pending review count
    result = await db.execute(
        select(func.count(CandidateDB.id)).where(CandidateDB.status == "new")
    )
    pending = result.scalar() or 0
    
    return TopMatchesResponse(
        top_candidates=top_candidates,
        jobs_with_matches=jobs_with_matches,
        star_candidates=star_candidates,
        total_pending_review=pending
    )

