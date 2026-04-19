"""
Search and Matching API Routes with PostgreSQL
"""
import asyncio
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.adapters import EmbeddingService, LLMEngine, QdrantRepository
from app.core.database import get_db
from app.db.models import CandidateDB, JobProfileDB, MatchResultDB
from app.domain import DEFAULT_SCORING_CONFIG, ScoringService
from app.api.routes.auth import get_current_active_user, UserResponse

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


class InterviewQuestion(BaseModel):
    tipo: str  # validar_logro | explorar_brecha | validar_inferencia
    pregunta: str


class MatchResultResponse(BaseModel):
    candidate_id: str
    full_name: str
    overall_score: float
    experience_score: float
    education_score: float
    skills_score: float
    dimension_scores: dict = Field(default_factory=dict)
    explanation: str
    recommendation: str = "Considerar"
    missing_skills: List[str]
    bonus_skills: List[str]
    relevant_experience_years: Optional[float] = None   # LLM-extracted years in relevant roles
    guia_entrevista: List[InterviewQuestion] = Field(default_factory=list)


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


# ============ Dependencies (module-level singletons) ============

_qdrant_repo: Optional[QdrantRepository] = None
_embedding_service: Optional[EmbeddingService] = None
_llm_engine: Optional[LLMEngine] = None


def get_qdrant_repo() -> QdrantRepository:
    global _qdrant_repo
    if _qdrant_repo is None:
        _qdrant_repo = QdrantRepository()
    return _qdrant_repo


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def get_llm_engine() -> LLMEngine:
    global _llm_engine
    if _llm_engine is None:
        _llm_engine = LLMEngine()
    return _llm_engine


# ============ Endpoints ============

@router.post("/semantic", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    """
    Perform semantic search for candidates.
    
    Uses vector similarity to find candidates matching the query intent,
    not just keyword matches.
    """
    # Generate query embedding
    query_embedding = await embedder.embed_text(request.query)
    
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
    current_user: UserResponse = Depends(get_current_active_user),
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
    # Embed once — all 3 vectors use the same query text
    emb = await embedder.embed_text(request.query)
    query_vectors = {"skills": emb, "experience": emb, "summary": emb}
    
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
    current_user: UserResponse = Depends(get_current_active_user),
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
    
    # Build per-dimension query texts aligned with how CVs were indexed
    required_skills = job.required_skills or []
    preferred_skills = job.preferred_skills or []
    all_skills = required_skills + preferred_skills
    responsibilities = getattr(job, "responsibilities", None) or []
    key_objectives = getattr(job, "key_objectives", None) or []
    required_languages = getattr(job, "required_languages", None) or []

    # skills query — mirrors the CV "Habilidades y tecnologías: ..." format
    _lang_suffix = ""
    if required_languages:
        _lang_parts = [f"{l.get('idioma','')} {l.get('nivel','')}" for l in required_languages[:3] if l.get('idioma')]
        if _lang_parts:
            _lang_suffix = f" | Idiomas: {', '.join(_lang_parts)}"
    skills_query = (
        f"Habilidades y tecnologías requeridas: {', '.join(all_skills[:20])}{_lang_suffix}"
        if all_skills else job.title + _lang_suffix
    )

    # experience query — mirrors the CV "Experiencia profesional: ..." format
    exp_parts = [f"Puesto: {job.title}"]
    if getattr(job, "seniority_level", None):
        exp_parts.append(f"Nivel: {job.seniority_level}")
    if job.min_experience_years:
        exp_parts.append(f"{job.min_experience_years} años de experiencia mínima")
    if responsibilities:
        exp_parts.append(f"Responsabilidades: {'. '.join(responsibilities[:5])}")
    if key_objectives:
        exp_parts.append(f"Objetivos clave: {'. '.join(key_objectives[:3])}")
    experience_query = "Experiencia profesional requerida: " + ". ".join(exp_parts)

    # education query — mirrors the CV "Formación académica: ..." format
    _EDU_LABELS = {
        "bachelor": "Bachiller o Licenciatura",
        "master": "Maestría o Máster",
        "phd": "Doctorado",
        "high_school": "Secundaria",
        "associate": "Técnico Superior",
    }
    edu_parts = []
    if getattr(job, "education_level", None):
        edu_parts.append(f"Formación mínima: {_EDU_LABELS.get(job.education_level, job.education_level)}")
    if getattr(job, "industry", None):
        edu_parts.append(f"Sector: {job.industry}")
    if required_skills:
        edu_parts.append(f"Conocimientos técnicos requeridos: {', '.join(required_skills[:8])}")
    education_query = (
        "Formación académica requerida: " + ". ".join(edu_parts)
        if edu_parts else skills_query
    )

    # summary query — mirrors the CV "Candidato: ..." summary format
    top_req = ", ".join(required_skills[:5]) if required_skills else ""
    summary_query = (
        f"Perfil buscado para {job.title}"
        + (f" ({job.seniority_level})" if getattr(job, "seniority_level", None) else "")
        + (f" en {job.industry}" if getattr(job, "industry", None) else "")
        + ". "
        + (f"{job.description} " if job.description else "")
        + (f"Habilidades clave: {top_req}." if top_req else "")
    )

    # Embed all 4 queries in parallel (education added)
    skills_emb, experience_emb, education_emb, summary_emb = await asyncio.gather(
        embedder.embed_text(skills_query),
        embedder.embed_text(experience_query),
        embedder.embed_text(education_query),
        embedder.embed_text(summary_query),
    )

    query_vectors = {
        "skills": skills_emb,
        "experience": experience_emb,
        "education": education_emb,
        "summary": summary_emb,
    }

    # Hybrid search with RRF fusion, filtered to this job's CVs
    search_results = []
    try:
        search_results = await qdrant.hybrid_search(
            query_vectors=query_vectors,
            limit=request.limit,
            job_id_filter=str(request.job_id),
        )
    except Exception as e:
        logger.warning(f"Qdrant hybrid search failed: {e}")

    # Resolve scoring weights — use job-specific config or fall back to global defaults
    # Validate dimensions against allowed set to prevent config injection
    ALLOWED_DIMENSIONS = {"skills", "experience", "education"}
    scoring_dims = job.scoring_config or [d.model_dump() for d in DEFAULT_SCORING_CONFIG]
    raw_weights = {}
    for d in scoring_dims:
        dim = d.get("dimension", "")
        w = d.get("weight", 0)
        if dim in ALLOWED_DIMENSIONS and isinstance(w, (int, float)) and 0 <= w <= 1:
            raw_weights[dim] = w
    # Fall back to defaults if config is empty or all invalid
    if not raw_weights:
        raw_weights = {d.dimension: d.weight for d in DEFAULT_SCORING_CONFIG}
    # Normalize so weights always sum to 1
    total_w = sum(raw_weights.values()) or 1
    weights = {dim: w / total_w for dim, w in raw_weights.items()}

    def compute_overall(skills_score: float, experience_score: float, education_score: float) -> float:
        dim_scores = {"skills": skills_score, "experience": experience_score, "education": education_score}
        return sum(dim_scores.get(dim, 0) * w for dim, w in weights.items())

    # Build candidate pool:
    # - Primary: Qdrant vector search (semantic similarity, scoped to job)
    # - Fallback: DB query when Qdrant returns nothing (e.g. new candidates not yet indexed)
    candidate_pool: List[CandidateDB] = []

    if search_results:
        ids = [UUID(cid) for cid, _, _ in search_results]
        batch = await db.execute(select(CandidateDB).where(CandidateDB.id.in_(ids)))
        by_id = {str(c.id): c for c in batch.scalars().all()}
        # Preserve Qdrant ranking order
        candidate_pool = [by_id[cid] for cid, _, _ in search_results if cid in by_id]
    else:
        logger.info("No Qdrant results — using DB fallback for matching")
        all_result = await db.execute(
            select(CandidateDB).where(CandidateDB.job_id == request.job_id).limit(request.limit)
        )
        candidate_pool = list(all_result.scalars().all())

    required_skills_lower = set(s.lower() for s in (job.required_skills or []))
    preferred_skills_lower = set(s.lower() for s in (job.preferred_skills or []))

    # Build rich job description text for the LLM — includes all available context
    _job_desc_parts = []
    if job.description:
        _job_desc_parts.append(job.description)
    if getattr(job, "industry", None):
        _job_desc_parts.append(f"Industria/Sector: {job.industry}")
    if getattr(job, "work_modality", None):
        _modality = {"remote": "Remoto", "hybrid": "Híbrido", "onsite": "Presencial"}
        _job_desc_parts.append(f"Modalidad: {_modality.get(job.work_modality, job.work_modality)}")
    if getattr(job, "education_level", None):
        _edu_labels = {"bachelor": "Bachiller/Licenciatura", "master": "Maestría",
                       "phd": "Doctorado", "high_school": "Secundaria"}
        _job_desc_parts.append(f"Educación mínima requerida: {_edu_labels.get(job.education_level, job.education_level)}")
    if responsibilities:
        _job_desc_parts.append(f"Responsabilidades principales: {'; '.join(responsibilities[:5])}")
    if key_objectives:
        _job_desc_parts.append(f"Objetivos clave: {'; '.join(key_objectives[:3])}")
    if required_languages:
        _lang_strs = []
        for _l in required_languages:
            _idioma = _l.get("idioma", "")
            _nivel = _l.get("nivel", "")
            _obligatorio = _l.get("obligatorio", True)
            if _idioma:
                _lang_strs.append(f"{_idioma} {_nivel}" + (" (obligatorio)" if _obligatorio else " (deseable)"))
        if _lang_strs:
            _job_desc_parts.append(f"Idiomas requeridos: {'; '.join(_lang_strs)}")
    job_description_text = "\n".join(_job_desc_parts) if _job_desc_parts else job.title

    def _skill_matches(candidate_skill: str, target_skill: str) -> bool:
        """Fuzzy skill match: handles abbreviations, substrings, common synonyms."""
        c = candidate_skill.lower().strip()
        t = target_skill.lower().strip()
        if c == t:
            return True
        # Substring in either direction
        if len(t) > 2 and (t in c or c in t):
            return True
        # Common tech abbreviations / synonyms
        _SYNONYMS: dict[str, set[str]] = {
            "javascript": {"js", "es6", "ecmascript"},
            "typescript": {"ts"},
            "python": {"python 3", "python3", "py"},
            "machine learning": {"ml", "aprendizaje automático"},
            "deep learning": {"dl", "redes neuronales"},
            "artificial intelligence": {"ia", "ai", "inteligencia artificial"},
            "natural language processing": {"nlp", "procesamiento de lenguaje"},
            "business intelligence": {"bi", "inteligencia de negocios"},
            "power bi": {"powerbi", "power-bi"},
            "sql server": {"mssql", "microsoft sql server", "t-sql"},
            "postgresql": {"postgres", "psql"},
            "kubernetes": {"k8s"},
            "excel": {"microsoft excel", "ms excel"},
            "microsoft office": {"office", "ms office"},
            "scrum": {"agile", "metodología ágil"},
        }
        for canonical, aliases in _SYNONYMS.items():
            all_forms = aliases | {canonical}
            if c in all_forms and t in all_forms:
                return True
        return False

    # Score each candidate using LLM reasoning (chain-of-thought).
    # Candidates are evaluated in parallel — up to LLM_MATCH_CONCURRENCY at a time.
    # This reduces wall-clock time from (N × T) to roughly (N/concurrency × T).
    LLM_MATCH_CONCURRENCY = 3  # matches OLLAMA_NUM_PARALLEL in docker-compose
    _sem = asyncio.Semaphore(LLM_MATCH_CONCURRENCY)

    async def _score_candidate(candidate: CandidateDB) -> MatchResultResponse:
        async with _sem:
            candidate_skills_lower = set(s.lower() for s in (candidate.skills or []))

            reasoning = await llm.reason_candidate_match(
                candidate_raw_text=candidate.raw_text or "",
                candidate_skills=candidate.skills or [],
                job_title=job.title,
                job_description=job_description_text,
                required_skills=job.required_skills or [],
                preferred_skills=job.preferred_skills or [],
                min_experience_years=job.min_experience_years or 0,
            )

            skills_score     = reasoning["skills_score"]
            experience_score = reasoning["experience_score"]
            education_score  = reasoning["education_score"]
            explanation      = reasoning["explanation"]
            recommendation   = reasoning["recommendation"]
            overall_score    = compute_overall(skills_score, experience_score, education_score)

            missing = [
                s for s in (job.required_skills or [])
                if not any(_skill_matches(cs, s) for cs in candidate_skills_lower)
            ]
            bonus = [
                s for s in (candidate.skills or [])
                if any(_skill_matches(s, ps) for ps in preferred_skills_lower)
            ]

            guia_raw = reasoning.get("guia_entrevista", [])
            guia = [
                InterviewQuestion(tipo=q.get("tipo", "validar_logro"), pregunta=q.get("pregunta", ""))
                for q in (guia_raw if isinstance(guia_raw, list) else [])
                if q.get("pregunta")
            ][:3]

            rel_years = reasoning.get("relevant_experience_years")

            return MatchResultResponse(
                candidate_id=str(candidate.id),
                full_name=candidate.full_name,
                overall_score=round(min(overall_score, 100), 1),
                experience_score=round(experience_score, 1),
                education_score=round(education_score, 1),
                skills_score=round(skills_score, 1),
                dimension_scores={
                    "skills":     round(skills_score, 1),
                    "experience": round(experience_score, 1),
                    "education":  round(education_score, 1),
                },
                explanation=explanation,
                recommendation=recommendation,
                missing_skills=missing[:5],
                bonus_skills=bonus[:5],
                relevant_experience_years=rel_years,
                guia_entrevista=guia,
            )

    matches = list(await asyncio.gather(*[_score_candidate(c) for c in candidate_pool]))
    matches.sort(key=lambda x: x.overall_score, reverse=True)

    # ── Persist scores to match_results (upsert) ────────────────────────────
    try:
        from sqlalchemy import func as sqlfunc
        for m in matches:
            guia_json = [q.model_dump() for q in m.guia_entrevista] if m.guia_entrevista else []
            stmt = pg_insert(MatchResultDB).values(
                candidate_id=UUID(m.candidate_id),
                job_id=request.job_id,
                candidate_name=m.full_name,
                overall_score=m.overall_score,
                skills_score=m.skills_score,
                experience_score=m.experience_score,
                education_score=m.education_score,
                relevant_experience_years=m.relevant_experience_years,
                recommendation=m.recommendation,
                explanation=m.explanation,
                missing_skills=m.missing_skills,
                bonus_skills=m.bonus_skills,
                guia_entrevista=guia_json,
                scored_at=sqlfunc.now(),
            ).on_conflict_do_update(
                constraint="match_results_candidate_id_job_id_key",
                set_={
                    "candidate_name": m.full_name,
                    "overall_score": m.overall_score,
                    "skills_score": m.skills_score,
                    "experience_score": m.experience_score,
                    "education_score": m.education_score,
                    "relevant_experience_years": m.relevant_experience_years,
                    "recommendation": m.recommendation,
                    "explanation": m.explanation,
                    "missing_skills": m.missing_skills,
                    "bonus_skills": m.bonus_skills,
                    "guia_entrevista": guia_json,
                    "scored_at": sqlfunc.now(),
                }
            )
            await db.execute(stmt)
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist match scores: {e}")
        await db.rollback()

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
    current_user: UserResponse = Depends(get_current_active_user),
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
    current_user: UserResponse = Depends(get_current_active_user),
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
