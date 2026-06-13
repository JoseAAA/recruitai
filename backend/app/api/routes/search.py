"""
Search and Matching API Routes with PostgreSQL
"""
import asyncio
import logging
import re
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.adapters import EmbeddingService, LLMEngine, QdrantRepository
from app.adapters.llm_providers import LLMRateLimitError
from app.core.database import get_db
from app.core.config import settings
from app.core.privacy import AuditLogger, get_audit_logger
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
    # When False (default) the endpoint reuses fresh cached scores from
    # match_results — only candidates without a cached score (or whose data
    # changed after scoring) are re-evaluated by the LLM. Re-using cached
    # scores turns "Re-analizar IA" from minutes into seconds for unchanged
    # candidates. Set true to force a full re-score.
    force_refresh: bool = False


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


class CandidateExplanationResponse(BaseModel):
    """Explicación amigable de la evaluación IA, dirigida al candidato.

    Cumple el derecho a explicación del Reglamento de IA Perú (DS 115-2025-PCM):
    el candidato puede solicitar saber por qué fue evaluado de cierta forma, y
    la respuesta debe estar en lenguaje accesible.
    """
    candidate_id: str
    job_id: str
    candidate_name: str
    job_title: str
    explanation_for_candidate: str  # Texto plano, listo para enviar.
    generated_at: str


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
    audit: AuditLogger = Depends(get_audit_logger),
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
    embedder: EmbeddingService = Depends(get_embedding_service),
    llm: LLMEngine = Depends(get_llm_engine),
):
    """
    Match candidates against a specific job profile.

    Returns ranked candidates with detailed score breakdowns
    and AI-generated explanations.

    DS 115-2025-PCM: cada ejecución queda registrada en ``audit_logs`` porque
    el screening de CVs está clasificado como **riesgo alto**. El log captura
    qué reclutador disparó el matching, sobre qué vacante y con qué parámetros.
    El reclutador siempre conserva la decisión final (intervención humana
    obligatoria); el ranking es solo una sugerencia.
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

    # ``selectinload(experience, education)``: trae experiencias y educación
    # en queries adicionales batched (no N+1) para que el matcher las pase al
    # LLM como evidencia estructurada con fechas exactas. Crítico para la
    # precisión de ``relevant_experience_years`` y para evitar enviar
    # ``raw_text`` (que contiene PII).
    if search_results:
        ids = [UUID(cid) for cid, _, _ in search_results]
        batch = await db.execute(
            select(CandidateDB)
            .options(selectinload(CandidateDB.experience), selectinload(CandidateDB.education))
            .where(CandidateDB.id.in_(ids))
        )
        by_id = {str(c.id): c for c in batch.scalars().all()}
        # Preserve Qdrant ranking order
        candidate_pool = [by_id[cid] for cid, _, _ in search_results if cid in by_id]
    else:
        logger.info("No Qdrant results — using DB fallback for matching")
        all_result = await db.execute(
            select(CandidateDB)
            .options(selectinload(CandidateDB.experience), selectinload(CandidateDB.education))
            .where(CandidateDB.job_id == request.job_id)
            .limit(request.limit)
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

    def _word_contains(haystack: str, needle: str) -> bool:
        """True si ``needle`` aparece como palabra completa dentro de ``haystack``.

        Usa límites de palabra que tratan ``+``/``#`` como parte del token para
        que "c" no coincida dentro de "c++"/"c#". Evita el falso positivo
        clásico de subcadenas: "java" ya NO coincide con "javascript".
        """
        pattern = rf"(?<![\w+#]){re.escape(needle)}(?![\w+#])"
        return re.search(pattern, haystack) is not None

    def _skill_matches(candidate_skill: str, target_skill: str) -> bool:
        """Fuzzy skill match: handles abbreviations, word-boundary substrings, synonyms."""
        c = candidate_skill.lower().strip()
        t = target_skill.lower().strip()
        if c == t:
            return True
        # Coincidencia por palabra completa en cualquier dirección:
        # "sql" ✓ "sql server", "react" ✓ "react native",
        # pero "java" ✗ "javascript" (antes la subcadena cruda daba match).
        if len(t) > 2 and (_word_contains(c, t) or _word_contains(t, c)):
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
    # Configurable in .env (debe coincidir con OLLAMA_NUM_PARALLEL en docker-compose).
    _sem = asyncio.Semaphore(settings.LLM_MATCH_CONCURRENCY)

    def _build_experience_payload(candidate: CandidateDB) -> list[dict]:
        """Serializa las entradas de experiencia para el matcher LLM.

        Devuelve dicts simples (no ORM) para evitar acoplar el adaptador al
        modelo de SQLAlchemy y para que el matcher reciba sólo lo que necesita:
        cargo, empresa, fechas y descripción.
        """
        entries: list[dict] = []
        for exp in candidate.experience or []:
            fecha_fin = (
                "Presente"
                if exp.is_current
                else (str(exp.end_date) if exp.end_date else None)
            )
            entries.append(
                {
                    "cargo": exp.title,
                    "empresa": exp.company,
                    "fecha_inicio": str(exp.start_date) if exp.start_date else None,
                    "fecha_fin": fecha_fin,
                    "descripcion": exp.description or "",
                }
            )
        return entries

    def _build_education_payload(candidate: CandidateDB) -> list[dict]:
        """Serializa educación + certificaciones. Sin PII del candidato:
        instituciones y grados son datos públicos de su trayectoria, no
        información personal identificatoria."""
        entries: list[dict] = []
        for edu in candidate.education or []:
            entries.append(
                {
                    "institution": edu.institution,
                    "degree": edu.degree,
                    "field_of_study": edu.field_of_study,
                    "education_type": getattr(edu, "education_type", "educacion"),
                    "degree_status": getattr(edu, "degree_status", None),
                    "start_date": str(edu.start_date) if edu.start_date else None,
                    "end_date": str(edu.end_date) if edu.end_date else None,
                }
            )
        return entries

    # Candidatos cuya evaluación IA no pudo ejecutarse (cuota del proveedor
    # agotada). Sus resultados se devuelven marcados como pendientes y NO se
    # persisten en match_results — así el próximo "Analizar con IA" los
    # re-evalúa de verdad en lugar de servir basura desde el caché.
    degraded_ids: set[str] = set()

    async def _score_candidate(candidate: CandidateDB) -> MatchResultResponse:
        async with _sem:
            candidate_skills_lower = set(s.lower() for s in (candidate.skills or []))

            # Principio de minimización (LPDP Art. 6.4): NO pasamos raw_text,
            # nombre, email, teléfono, DNI ni dirección. El LLM evalúa solo
            # competencia profesional, no identidad. ``summary`` se envía si
            # existe y se asume libre de PII (lo extrae el LLM en upload con
            # masking activo cuando aplica).
            try:
                reasoning = await llm.reason_candidate_match(
                    candidate_skills=candidate.skills or [],
                    job_title=job.title,
                    job_description=job_description_text,
                    required_skills=job.required_skills or [],
                    preferred_skills=job.preferred_skills or [],
                    min_experience_years=job.min_experience_years or 0,
                    candidate_experience=_build_experience_payload(candidate),
                    candidate_education=_build_education_payload(candidate),
                    candidate_languages=candidate.idiomas or None,
                    candidate_summary=candidate.summary,
                )
            except LLMRateLimitError:
                degraded_ids.add(str(candidate.id))
                logger.warning(
                    f"Match sin IA para {candidate.id} (cuota agotada) — "
                    "marcado como pendiente, no se persiste"
                )
                reasoning = {
                    "skills_score": 0.0,
                    "experience_score": 0.0,
                    "education_score": 0.0,
                    "explanation": (
                        "Este candidato aún no pudo ser evaluado por la IA "
                        "(el sistema de análisis estaba saturado). Vuelve a "
                        "ejecutar 'Analizar con IA' en unos minutos."
                    ),
                    "recommendation": "Considerar",
                    "relevant_experience_years": None,
                    "guia_entrevista": [],
                }

            skills_score     = reasoning["skills_score"]
            experience_score = reasoning["experience_score"]
            education_score  = reasoning["education_score"]
            explanation      = reasoning["explanation"]
            recommendation   = reasoning["recommendation"]
            overall_score    = compute_overall(skills_score, experience_score, education_score)

            # Coherencia puntaje↔etiqueta: el LLM a veces dice "Considerar"
            # con un total de 11/100, lo que confunde al reclutador. Regla
            # solo-degradante (nunca sube una recomendación): total < 30 ⇒
            # "No recomendado". La decisión final sigue siendo humana (DS 115).
            if overall_score < 30 and recommendation != "No recomendado":
                recommendation = "No recomendado"

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

    # ── Cache reuse ─────────────────────────────────────────────────────────
    # Query persisted match_results for this job. A cached row is "fresh" if
    # it was scored AFTER the candidate's last update AND after the job's
    # last update. Candidates with fresh cached rows skip the LLM call.
    # Massive UX win: clicking "Analizar IA" twice in a row no longer
    # re-runs the LLM on every candidate. Set force_refresh=true to override.
    cached_by_id: dict[str, MatchResultResponse] = {}
    if not request.force_refresh and candidate_pool:
        cand_ids = [c.id for c in candidate_pool]
        cached_rows = await db.execute(
            select(MatchResultDB).where(
                MatchResultDB.job_id == request.job_id,
                MatchResultDB.candidate_id.in_(cand_ids),
            )
        )
        candidates_by_id = {c.id: c for c in candidate_pool}
        job_updated_at = getattr(job, "updated_at", None)
        for row in cached_rows.scalars().all():
            cand = candidates_by_id.get(row.candidate_id)
            if not cand:
                continue
            scored_at = row.scored_at
            cand_updated = getattr(cand, "updated_at", None)
            # Skip stale cache: candidate or job updated after the score was
            # produced. Fall through to the LLM in that case.
            if not scored_at:
                continue
            if cand_updated and cand_updated > scored_at:
                continue
            if job_updated_at and job_updated_at > scored_at:
                continue
            guia = [
                InterviewQuestion(tipo=q.get("tipo", "validar_logro"), pregunta=q.get("pregunta", ""))
                for q in (row.guia_entrevista or [])
                if isinstance(q, dict) and q.get("pregunta")
            ][:3]
            cached_by_id[str(row.candidate_id)] = MatchResultResponse(
                candidate_id=str(row.candidate_id),
                # Nombre fresco de la DB primero: si el reclutador corrigió el
                # nombre después del último scoring, el caché no debe mostrarlo viejo.
                full_name=cand.full_name or row.candidate_name,
                overall_score=row.overall_score,
                experience_score=row.experience_score or 0,
                education_score=row.education_score or 0,
                skills_score=row.skills_score or 0,
                dimension_scores={
                    "skills":     round(row.skills_score or 0, 1),
                    "experience": round(row.experience_score or 0, 1),
                    "education":  round(row.education_score or 0, 1),
                },
                explanation=row.explanation or "",
                recommendation=row.recommendation or "Considerar",
                missing_skills=row.missing_skills or [],
                bonus_skills=row.bonus_skills or [],
                relevant_experience_years=row.relevant_experience_years,
                guia_entrevista=guia,
            )
        if cached_by_id:
            logger.info(
                f"Match cache hit: {len(cached_by_id)}/{len(candidate_pool)} "
                f"candidates reused, {len(candidate_pool) - len(cached_by_id)} need LLM"
            )

    candidates_to_score = [c for c in candidate_pool if str(c.id) not in cached_by_id]
    fresh_matches = list(
        await asyncio.gather(*[_score_candidate(c) for c in candidates_to_score])
    ) if candidates_to_score else []

    # Combine cached + freshly-scored, preserving Qdrant ranking order.
    matches = []
    for c in candidate_pool:
        cid = str(c.id)
        if cid in cached_by_id:
            matches.append(cached_by_id[cid])
    matches.extend(fresh_matches)
    matches.sort(key=lambda x: x.overall_score, reverse=True)

    # ── Persist scores to match_results (upsert) ────────────────────────────
    try:
        from sqlalchemy import func as sqlfunc
        # Only persist freshly-scored matches; cached ones are already in DB
        # and re-writing them would bump scored_at without any new info.
        # Degraded results (cuota agotada) NO se persisten: el caché los
        # daría por buenos y el candidato nunca recibiría evaluación real.
        for m in fresh_matches:
            if m.candidate_id in degraded_ids:
                continue
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

    # LPDP + DS 115-2025-PCM: registra la ejecución del matching IA. Este es
    # el evento más sensible legalmente — una decisión automatizada sobre
    # personas. El log nos permite reconstruir, ante una solicitud ARCO-P o
    # una inspección de la ANPD, qué candidatos fueron evaluados, por quién y
    # con qué parámetros. La llamada va después del cómputo para no romper la
    # respuesta si el insert falla (AuditLogger ya hace try/except interno).
    await audit.log_access(
        user_id=str(current_user.id),
        action="ai_match_executed",
        resource_type="job",
        resource_id=str(job.id),
        details={
            "job_title": job.title,
            "candidates_evaluated": len(matches),
            "candidates_from_cache": len(cached_by_id),
            "force_refresh": request.force_refresh,
            "model": settings.MATCH_MODEL,
            "llm_provider": settings.LLM_PROVIDER,
        },
    )

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
        raise HTTPException(status_code=404, detail="Candidato no encontrado")
    if not job:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")

    # Usa el match_result persistido (calculado por /match) — datos reales del
    # análisis IA. Antes este endpoint devolvía valores inventados (70/70/75
    # hardcodeados para Experiencia/Educación/Comunicación) para TODOS los
    # candidatos, lo que fabricaba información frente al reclutador.
    m_result = await db.execute(
        select(MatchResultDB).where(
            MatchResultDB.candidate_id == candidate_id,
            MatchResultDB.job_id == job_id,
        )
    )
    match = m_result.scalar_one_or_none()

    if match:
        radar_data = [
            RadarDataPoint(axis="Habilidades", candidate_value=round(match.skills_score or 0, 1)),
            RadarDataPoint(axis="Experiencia", candidate_value=round(match.experience_score or 0, 1)),
            RadarDataPoint(axis="Educación", candidate_value=round(match.education_score or 0, 1)),
        ]
        gap_analysis = {
            "missing_skills": (match.missing_skills or [])[:10],
            "bonus_skills": (match.bonus_skills or [])[:10],
            "recommendation": match.recommendation or "Considerar",
        }
    else:
        # Sin análisis IA previo: solo podemos comparar habilidades de forma
        # literal. No inventamos ejes que no medimos.
        candidate_skills = set(s.lower() for s in (candidate.skills or []))
        required_skills = set(s.lower() for s in (job.required_skills or []))
        if required_skills:
            skills_score = (len(candidate_skills & required_skills) / len(required_skills)) * 100
        else:
            skills_score = 100.0  # sin requisitos no hay brecha que penalizar
        radar_data = [
            RadarDataPoint(axis="Habilidades", candidate_value=round(skills_score, 1)),
        ]
        gap_analysis = {
            "missing_skills": sorted(required_skills - candidate_skills)[:10],
            "bonus_skills": sorted(candidate_skills - required_skills)[:10],
            "recommendation": "Ejecuta 'Analizar con IA' para una evaluación completa",
        }

    return ComparisonResponse(
        candidate_id=str(candidate_id),
        candidate_name=candidate.full_name,
        radar_data=radar_data,
        gap_analysis=gap_analysis,
    )


@router.post("/explain/{candidate_id}/{job_id}", response_model=CandidateExplanationResponse)
async def explain_decision_to_candidate(
    candidate_id: UUID,
    job_id: UUID,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    audit: AuditLogger = Depends(get_audit_logger),
    llm: LLMEngine = Depends(get_llm_engine),
):
    """Genera la explicación de la evaluación IA en lenguaje accesible al candidato.

    Cumple el **derecho a explicación** del Reglamento de IA peruano
    (DS 115-2025-PCM, vigente desde el 22-ene-2026). El texto generado:

    - No menciona modelos, prompts, scores ni tecnicismos.
    - Es honesto sobre brechas, pero constructivo.
    - Recuerda explícitamente que la decisión final la toma una persona.

    El reclutador copia el texto resultante y lo envía al candidato cuando
    este solicita saber por qué fue evaluado de cierta forma. La acción queda
    registrada en ``audit_logs`` para demostrar a la ANPD que el derecho fue
    atendido.
    """
    # Cargar el match_result persistido (ya calculado por /match)
    from datetime import datetime as _dt
    result = await db.execute(
        select(MatchResultDB).where(
            MatchResultDB.candidate_id == candidate_id,
            MatchResultDB.job_id == job_id,
        )
    )
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No hay evaluación IA registrada para este candidato en esta "
                "vacante. Ejecuta primero 'Analizar con IA' en el ranking."
            ),
        )

    # Necesitamos el título de la vacante para personalizar
    j_res = await db.execute(select(JobProfileDB).where(JobProfileDB.id == job_id))
    job = j_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")

    candidate_name = match.candidate_name or "candidato"

    explanation_text = await llm.explain_for_candidate(
        candidate_name=candidate_name,
        job_title=job.title,
        overall_score=match.overall_score or 0,
        recommendation=match.recommendation or "",
        explanation_internal=match.explanation or "",
        missing_skills=match.missing_skills or [],
        bonus_skills=match.bonus_skills or [],
    )

    # Auditoría: ejercicio del derecho a explicación.
    await audit.log_access(
        user_id=str(current_user.id),
        action="ai_explanation_generated_for_candidate",
        resource_type="candidate",
        resource_id=str(candidate_id),
        details={
            "job_id": str(job_id),
            "job_title": job.title,
            "candidate_name": candidate_name,
        },
    )

    return CandidateExplanationResponse(
        candidate_id=str(candidate_id),
        job_id=str(job_id),
        candidate_name=candidate_name,
        job_title=job.title,
        explanation_for_candidate=explanation_text,
        generated_at=_dt.utcnow().isoformat() + "Z",
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
