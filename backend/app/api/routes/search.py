"""
Search and Matching API Routes with PostgreSQL
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import EmbeddingService, LLMEngine, QdrantRepository
from app.core.database import get_db
from app.db.models import CandidateDB, JobProfileDB
from app.domain import ScoringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Search & Matching"])


# ============ Request/Response Schemas ============

class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural language search query")
    job_id: Optional[UUID] = Field(None, description="Job to match against")
    min_score: float = Field(0.5, ge=0, le=1)
    limit: int = Field(20, ge=1, le=100)


class SearchResult(BaseModel):
    candidate_id: str
    full_name: str
    score: float
    skills: List[str]
    experience_years: float


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    query: str


class MatchRequest(BaseModel):
    job_id: UUID
    candidate_ids: Optional[List[UUID]] = None
    limit: int = Field(20, ge=1, le=100)


class MatchResultResponse(BaseModel):
    candidate_id: str
    full_name: str
    overall_score: float
    experience_score: float
    education_score: float
    skills_score: float
    explanation: str
    missing_skills: List[str]
    bonus_skills: List[str]


class MatchResponse(BaseModel):
    job_id: UUID
    job_title: str
    matches: List[MatchResultResponse]
    total: int


class RadarDataPoint(BaseModel):
    axis: str
    candidate_value: float
    ideal_value: float = 100.0


class ComparisonResponse(BaseModel):
    candidate_id: str
    candidate_name: str
    radar_data: List[RadarDataPoint]
    gap_analysis: dict


# ============ Dependencies ============

def get_qdrant_repo() -> QdrantRepository:
    return QdrantRepository()


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


def get_llm_engine() -> LLMEngine:
    return LLMEngine()


# ============ Endpoints ============

@router.post("/semantic", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    """
    Perform semantic search for candidates.
    
    Uses vector similarity to find candidates matching the query intent,
    not just keyword matches.
    """
    # Generate query embedding
    query_embedding = embedder.embed_text(request.query)
    
    # Search in Qdrant
    results = await qdrant.search_similar(
        query_vector=query_embedding,
        vector_name="skills",  # Primary search on skills
        limit=request.limit,
        score_threshold=request.min_score,
    )
    
    search_results = []
    for candidate_id, score, payload in results:
        search_results.append(SearchResult(
            candidate_id=candidate_id,
            full_name=payload.get("full_name", "Unknown"),
            score=round(score, 3),
            skills=payload.get("skills", []),
            experience_years=payload.get("experience_years", 0),
        ))
    
    return SearchResponse(
        results=search_results,
        total=len(search_results),
        query=request.query,
    )


@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search(
    request: SearchRequest,
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    """
    Perform hybrid search using RRF fusion.
    
    Combines semantic similarity across multiple aspects:
    - Skills
    - Experience
    - Summary/Profile
    """
    # Generate embeddings for query
    query_vectors = {
        "skills": embedder.embed_text(request.query),
        "experience": embedder.embed_text(request.query),
        "summary": embedder.embed_text(request.query),
    }
    
    # Hybrid search with RRF fusion
    results = await qdrant.hybrid_search(
        query_vectors=query_vectors,
        limit=request.limit,
    )
    
    search_results = []
    for candidate_id, score, payload in results:
        search_results.append(SearchResult(
            candidate_id=candidate_id,
            full_name=payload.get("full_name", "Unknown"),
            score=round(score, 3),
            skills=payload.get("skills", []),
            experience_years=payload.get("experience_years", 0),
        ))
    
    return SearchResponse(
        results=search_results,
        total=len(search_results),
        query=request.query,
    )


@router.post("/match", response_model=MatchResponse)
async def match_candidates_to_job(
    request: MatchRequest,
    db: AsyncSession = Depends(get_db),
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
    embedder: EmbeddingService = Depends(get_embedding_service),
    llm: LLMEngine = Depends(get_llm_engine),
):
    """
    Match candidates against a specific job profile.
    
    Returns ranked candidates with detailed score breakdowns
    and AI-generated explanations.
    """
    # Get job profile from database
    result = await db.execute(
        select(JobProfileDB).where(JobProfileDB.id == request.job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job profile not found"
        )
    
    # Build query from job requirements
    job_query = f"{job.title}. {' '.join(job.required_skills or [])}. {job.description or ''}"
    
    # Generate embedding for job
    job_embedding = embedder.embed_text(job_query)
    
    # Search for matching candidates in Qdrant
    search_results = []
    try:
        search_results = await qdrant.search_similar(
            query_vector=job_embedding,
            vector_name="skills",
            limit=request.limit,
        )
    except Exception as e:
        logger.warning(f"Qdrant search failed: {e}")
    
    # FALLBACK: If Qdrant returns no results, fetch all candidates from DB
    if not search_results:
        logger.info("No Qdrant results, using database fallback for matching")
        all_candidates_result = await db.execute(
            select(CandidateDB).limit(request.limit)
        )
        all_candidates = all_candidates_result.scalars().all()
        
        matches = []
        for candidate in all_candidates:
            # Calculate scores based on skills overlap
            candidate_skills = set(s.lower() for s in (candidate.skills or []))
            required_skills = set(s.lower() for s in (job.required_skills or []))
            preferred_skills = set(s.lower() for s in (job.preferred_skills or []))
            
            matching_required = len(candidate_skills & required_skills)
            matching_preferred = len(candidate_skills & preferred_skills)
            total_required = len(required_skills) or 1
            
            skills_score = (matching_required / total_required) * 100
            overall_score = skills_score * 0.7 + matching_preferred * 5  # Bonus for preferred skills
            
            missing = list(required_skills - candidate_skills)
            bonus = list(candidate_skills & preferred_skills)
            
            matches.append(MatchResultResponse(
                candidate_id=str(candidate.id),
                full_name=candidate.full_name,
                overall_score=round(min(overall_score, 100), 1),
                experience_score=70.0,
                education_score=70.0,
                skills_score=round(skills_score, 1),
                explanation=f"Candidato con {len(candidate_skills)} habilidades. Coincide {matching_required}/{total_required} requeridas.",
                missing_skills=missing[:5],
                bonus_skills=bonus[:5],
            ))
        
        # Sort by overall score
        matches.sort(key=lambda x: x.overall_score, reverse=True)
        
        return MatchResponse(
            job_id=job.id,
            job_title=job.title,
            matches=matches,
            total=len(matches),
        )
    
    # Calculate detailed scores for each match from Qdrant
    matches = []
    for candidate_id, vector_score, payload in search_results:
        # Get full candidate data from database
        c_result = await db.execute(
            select(CandidateDB).where(CandidateDB.id == UUID(candidate_id))
        )
        candidate = c_result.scalar_one_or_none()
        
        if not candidate:
            continue
        
        # Simple scoring based on skills overlap
        candidate_skills = set(s.lower() for s in (candidate.skills or []))
        required_skills = set(s.lower() for s in (job.required_skills or []))
        preferred_skills = set(s.lower() for s in (job.preferred_skills or []))
        
        matching_required = len(candidate_skills & required_skills)
        matching_preferred = len(candidate_skills & preferred_skills)
        total_required = len(required_skills) or 1
        
        skills_score = (matching_required / total_required) * 100
        overall_score = skills_score * 0.7 + (vector_score * 100) * 0.3
        
        missing = list(required_skills - candidate_skills)
        bonus = list(candidate_skills & preferred_skills)
        
        matches.append(MatchResultResponse(
            candidate_id=candidate_id,
            full_name=candidate.full_name,
            overall_score=round(overall_score, 1),
            experience_score=70.0,  # Placeholder
            education_score=70.0,   # Placeholder
            skills_score=round(skills_score, 1),
            explanation=f"Candidato con {len(candidate_skills)} habilidades. Coincide {matching_required}/{total_required} requeridas.",
            missing_skills=missing[:5],
            bonus_skills=bonus[:5],
        ))
    
    # Sort by overall score
    matches.sort(key=lambda x: x.overall_score, reverse=True)
    
    return MatchResponse(
        job_id=job.id,
        job_title=job.title,
        matches=matches,
        total=len(matches),
    )


@router.get("/compare/{candidate_id}/{job_id}", response_model=ComparisonResponse)
async def get_comparison_data(
    candidate_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get radar chart comparison data for a candidate vs job.
    
    Returns data formatted for visualization.
    """
    # Get candidate from database
    c_result = await db.execute(
        select(CandidateDB).where(CandidateDB.id == candidate_id)
    )
    candidate = c_result.scalar_one_or_none()
    
    # Get job from database
    j_result = await db.execute(
        select(JobProfileDB).where(JobProfileDB.id == job_id)
    )
    job = j_result.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Simple scoring
    candidate_skills = set(s.lower() for s in (candidate.skills or []))
    required_skills = set(s.lower() for s in (job.required_skills or []))
    
    skills_score = (len(candidate_skills & required_skills) / max(len(required_skills), 1)) * 100
    
    radar_data = [
        RadarDataPoint(axis="Technical Skills", candidate_value=skills_score),
        RadarDataPoint(axis="Experience", candidate_value=70.0),
        RadarDataPoint(axis="Education", candidate_value=70.0),
        RadarDataPoint(axis="Leadership", candidate_value=70.0),
        RadarDataPoint(axis="Communication", candidate_value=75.0),
    ]
    
    missing = list(required_skills - candidate_skills)
    bonus = list(candidate_skills - required_skills)
    
    gap_analysis = {
        "missing_skills": missing[:10],
        "bonus_skills": bonus[:10],
        "recommendation": "Buen candidato" if skills_score >= 60 else "Revisar fit",
    }
    
    return ComparisonResponse(
        candidate_id=str(candidate_id),
        candidate_name=candidate.full_name,
        radar_data=radar_data,
        gap_analysis=gap_analysis,
    )


@router.get("/stats")
async def get_search_stats(
    db: AsyncSession = Depends(get_db),
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
):
    """Get search index statistics."""
    info = await qdrant.get_collection_info()
    
    # Count jobs from database
    result = await db.execute(select(JobProfileDB.id))
    total_jobs = len(result.all())
    
    return {
        "indexed_candidates": info.get("points_count", 0),
        "total_jobs": total_jobs,
        "collection_status": info.get("status", "unknown"),
    }
