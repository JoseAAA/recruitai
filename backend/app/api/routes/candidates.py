"""
Candidate Management API Routes with PostgreSQL persistence
"""
import hashlib
import logging
import re as _re
from datetime import date as date_type
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi.responses import Response

from app.adapters import EmbeddingService, LLMEngine, QdrantRepository
from app.adapters.llm_engine import PromptInjectionError
from app.adapters.llm_providers import LLMRateLimitError
from app.adapters.storage import StorageService, BUCKET_CVS
from app.core.privacy import AuditLogger, get_audit_logger
from app.core.usage import LLMUsageRecorder, get_usage_recorder
from app.adapters.document_extractor import DocumentExtractor, DocumentParsingError
from app.api.routes.auth import get_current_active_user, UserResponse
from app.core.database import get_db
from app.core.config import settings
from app.core.rate_limit import limit
from app.core.validators import validate_pdf_bytes, validate_docx_bytes
from app.db.models import CandidateDB, ExperienceEntryDB, EducationEntryDB
from app.domain import CandidateStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["Candidates"])


# ============ Safe Content-Type Helper ============

# Tipos MIME seguros derivados de la EXTENSIÓN validada del archivo. Nunca se
# confía en el Content-Type que declara el cliente al subir: un atacante
# autenticado puede subir un PDF-políglota (bytes %PDF válidos que pasan la
# validación estructural) con <script> en texto plano y declararlo como
# "text/html"; si luego se sirve inline en el preview, el navegador lo
# renderiza como HTML y ejecuta el script en el origen de la app (XSS
# almacenado → robo del token de sesión). Servimos siempre con el tipo que
# corresponde a la extensión real, y con X-Content-Type-Options: nosniff.
_SAFE_MEDIA_TYPES = {
    "pdf":  "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc":  "application/msword",
}


def _safe_media_type(filename: str) -> str:
    """Devuelve un Content-Type seguro según la extensión (ignora el del cliente)."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _SAFE_MEDIA_TYPES.get(ext, "application/octet-stream")


# ============ Date Parsing Helpers ============

import dateparser as _dateparser

# Localized markers that mean "still working here" — must short-circuit to None
# so they aren't accidentally parsed as today's date.
_ACTIVE_MARKERS = {
    'presente', 'actual', 'current', 'actualidad', 'a la fecha',
    'hasta hoy', 'en curso', 'hoy', 'vigente', 'actualmente',
    'present', 'now', 'ongoing', 'to date', 'till date', '',
}


def _safe_date(year: int, month: int) -> Optional[date_type]:
    """Build a date(year, month, 1) without raising on garbage values.

    The LLM occasionally emits malformed dates like ``2018-13`` or ``2018-00``
    when the source CV ambiguates a month. Returning None here keeps the
    upload pipeline resilient: a single bad date should leave the candidate
    importable (the recruiter can fix it via the experience editor) instead
    of failing the whole CV with a cryptic ``month must be in 1..12``.
    """
    if not (1 <= month <= 12):
        return None
    if year < 1900 or year > 2100:
        return None
    try:
        return date_type(year, month, 1)
    except ValueError:
        return None


def parse_date_str(s: Optional[str]) -> Optional[date_type]:
    """Parse date strings into a date object.

    Cheap regex first for the canonical YYYY-MM and YYYY-MM-DD shapes the LLM
    is supposed to emit. Anything else (Spanish abbreviations like "Set 2016"
    or "Agos 2019", Portuguese "Janeiro", typos, mixed punctuation) is handed
    to dateparser, which knows ~200 language variants. Returns None for null,
    "still ongoing" markers, or out-of-range months instead of raising.
    """
    if not s:
        return None
    s = s.strip()
    if s.lower() in _ACTIVE_MARKERS:
        return None
    # YYYY-MM-DD (LLM sometimes returns full ISO despite YYYY-MM instructions)
    m = _re.match(r'^(\d{4})-(\d{1,2})-\d{1,2}$', s)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)))
    # YYYY-MM
    m = _re.match(r'^(\d{4})-(\d{1,2})$', s)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)))
    # YYYY only
    if s.isdigit() and len(s) == 4:
        return _safe_date(int(s), 1)
    # Anything else → dateparser (Spanish/Portuguese/English variants).
    # "Agos" (4-letter agosto abbreviation) is dateparser's only blind spot.
    try:
        s_norm = _re.sub(r'\bAgos\b', 'Agosto', s, flags=_re.IGNORECASE)
        parsed = _dateparser.parse(s_norm, languages=['es', 'pt', 'en'])
        if parsed:
            return _safe_date(parsed.year, parsed.month)
    except Exception:
        pass
    return None


# ============ Request/Response Schemas ============

class CandidateResponse(BaseModel):
    id: UUID
    full_name: str
    email: Optional[str]
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    summary: Optional[str]
    skills: List[str]
    total_experience_years: float
    status: str
    job_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class CandidateDetailResponse(CandidateResponse):
    experience: List[dict]
    education: List[dict]
    idiomas: List[dict] = []
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
    job_id: Optional[UUID] = None


# ============ Dependencies (module-level singletons) ============

_doc_extractor: Optional[DocumentExtractor] = None
_embedding_service: Optional[EmbeddingService] = None
_llm_engine: Optional[LLMEngine] = None
_qdrant_repo: Optional[QdrantRepository] = None
_storage: Optional[StorageService] = None


def get_docling_extractor() -> DocumentExtractor:
    global _doc_extractor
    if _doc_extractor is None:
        _doc_extractor = DocumentExtractor()
    return _doc_extractor


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


def get_qdrant_repo() -> QdrantRepository:
    global _qdrant_repo
    if _qdrant_repo is None:
        _qdrant_repo = QdrantRepository()
    return _qdrant_repo


def get_storage() -> StorageService:
    global _storage
    if _storage is None:
        _storage = StorageService()
    return _storage


# ============ Helper Functions ============

def calculate_experience_years(experience_entries: List[ExperienceEntryDB]) -> float:
    """Calculate total years of non-overlapping professional experience.

    Uses interval merging so concurrent jobs are counted once, not doubled.
    Example: two jobs from 2021-2023 and 2022-2024 → 3 years, not 4.
    """
    from datetime import date as date_type
    today = date_type.today()

    # Build list of (start, end) intervals — only entries with a known start date
    intervals: list[tuple[date_type, date_type]] = []
    for exp in experience_entries:
        if not exp.start_date:
            continue
        end = today if (exp.is_current or not exp.end_date) else exp.end_date
        if end < exp.start_date:
            continue  # corrupted entry — skip
        intervals.append((exp.start_date, end))

    if not intervals:
        return 0.0

    # Sort by start date, then merge overlapping/adjacent intervals
    intervals.sort(key=lambda x: x[0])
    merged: list[tuple[date_type, date_type]] = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:               # overlaps or adjacent → extend
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    # Sum merged intervals in fractional years
    total_years = 0.0
    for start, end in merged:
        years = (end.year - start.year) + (end.month - start.month) / 12
        total_years += max(0.0, years)

    return round(total_years, 1)


# ============ Endpoints ============

@router.post("/upload", response_model=UploadResponse)
@limit("10/minute")
async def upload_cv(
    request: Request,
    file: UploadFile = File(...),
    job_id: Optional[UUID] = Form(None),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    audit: AuditLogger = Depends(get_audit_logger),
    recorder: LLMUsageRecorder = Depends(get_usage_recorder),
    embedder: EmbeddingService = Depends(get_embedding_service),
    llm: LLMEngine = Depends(get_llm_engine),
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
    docling: DocumentExtractor = Depends(get_docling_extractor),
    storage: StorageService = Depends(get_storage),
):
    """
    Upload and process a CV/Resume file.
    Uses Vision API for PDFs/images (better accuracy with varied formats).
    Falls back to text extraction for unsupported formats.
    """
    if not job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes asociar el CV a una vacante (job_id requerido)."
        )

    allowed_types = [".pdf", ".docx"]
    # Sanitize filename: strip path components, keep only basename
    import os as _os
    raw_filename = file.filename or "unknown"
    filename = _os.path.basename(raw_filename).replace("..", "").strip() or "unknown"

    file_ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido. Formatos aceptados: PDF, DOCX"
        )

    try:
        # Read file content
        content = await file.read()

        # ── Upload safety: MIME magic + structural / macro inspection ─────────
        # Delegates to ``app.core.validators`` which combines:
        #   * python-magic (real MIME from libmagic, defeats renamed payloads)
        #   * pikepdf      (rejects PDFs with /JS, /Launch, /OpenAction, /AA)
        #   * oletools     (rejects DOCX with VBA macros)
        # The previous 4-byte magic check let through PDFs with embedded
        # JavaScript and DOCX with macros — both real malware vectors.
        if file_ext == ".pdf":
            ok, reason = validate_pdf_bytes(content)
        else:
            ok, reason = validate_docx_bytes(content)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=reason or "Archivo rechazado por validación de seguridad.",
            )

        file_hash = hashlib.sha256(content).hexdigest()

        # ── Deduplication: same file + same job = update, not insert ──────────
        dup_query = select(CandidateDB).where(CandidateDB.file_hash == file_hash)
        if job_id:
            dup_query = dup_query.where(CandidateDB.job_id == job_id)
        dup_result = await db.execute(dup_query)
        existing_candidate = dup_result.scalar_one_or_none()
        if existing_candidate:
            logger.info(f"Duplicate file detected (hash={file_hash[:8]}…), returning existing record.")
            return UploadResponse(
                id=existing_candidate.id,
                filename=filename,
                status="duplicate",
                extracted_name=existing_candidate.full_name,
                skills_count=len(existing_candidate.skills or []),
                message="CV ya procesado anteriormente — se devuelve el perfil existente",
                job_id=job_id,
            )
        # ──────────────────────────────────────────────────────────────────────

        extracted = None
        raw_text = ""
        extraction_method = "docling"

        logger.info(f"File upload: {filename}, Extension: {file_ext}")
        logger.info(f"LLM_PROVIDER: {settings.LLM_PROVIDER}, EXTRACTION_MODEL: {getattr(settings, 'EXTRACTION_MODEL', 'Not set')}")
        
        # 1. Convert to Markdown using document extractor (PDF security scan included)
        # Medimos el tiempo de lectura del documento (preprocess_ms) por separado
        # del tiempo del LLM, para el KPI "tiempo total de procesar un CV".
        import time as _time
        hidden_fragments: list[str] = []
        preprocess_ms: int = 0
        extraction_usage: dict = {}
        try:
            logger.info(f"Starting document extraction for {filename}")
            _parse_t0 = _time.perf_counter()
            markdown_content, doc_meta = await docling.parse_bytes(content, filename)
            preprocess_ms = int((_time.perf_counter() - _parse_t0) * 1000)
            raw_text = markdown_content
            hidden_fragments = doc_meta.get("hidden_text_fragments", [])
            sec_warnings = doc_meta.get("security_warnings", [])
            if sec_warnings:
                logger.warning(
                    f"Document security findings for {filename}: "
                    + "; ".join(sec_warnings[:5])
                )

            # HARD BLOCK on hidden-content attack vectors. Legitimate CVs do
            # not contain white-on-white text, sub-1pt micro-font text, or
            # off-page text — these are exclusively used for prompt-injection
            # attacks (Kai Greshake "Inject My PDF", 2023). We reject before
            # the document text ever reaches the LLM.
            blocking_kinds = ("[TEXTO_BLANCO]", "[TEXTO_MICRO]", "[TEXTO_FUERA]")
            blocking_hits = [
                f for f in hidden_fragments
                if any(kind in f for kind in blocking_kinds) and len(f.strip()) > 25
            ]
            # PDF JavaScript or hidden-layer warnings are also blocking.
            for w in sec_warnings:
                if "JavaScript" in w or "capas opcionales" in w:
                    blocking_hits.append(w)
            if blocking_hits:
                logger.warning(
                    f"REJECTED upload {filename}: hidden-content attack vectors detected. "
                    f"First finding: {blocking_hits[0][:120]}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "ARCHIVO_RECHAZADO_SEGURIDAD: no procesamos este CV porque contiene "
                        "texto oculto que podría intentar manipular la IA. Pídele al "
                        "candidato que lo reenvíe limpio o expórtalo de nuevo desde Word."
                    ),
                )
            logger.info(f"Document extraction successful. Markdown length: {len(raw_text)}")
        except HTTPException:
            # Don't swallow our own deliberate rejections (e.g. ARCHIVO_RECHAZADO_SEGURIDAD)
            # — those carry the precise reason the user needs to fix their upload.
            raise
        except Exception as e:
            logger.error(f"Document extraction failed for {filename}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo leer el documento. Verifica que el archivo no esté protegido con contraseña ni dañado."
            )

        # 2. Extract JSON using LLM — injection patterns checked against visible
        #    text AND hidden PDF fragments (white text, metadata, off-page text)
        try:
            logger.info(f"Starting LLM extraction for {filename}")
            extracted = await llm.extract_resume(
                raw_text, filename=filename, hidden_fragments=hidden_fragments,
                usage_out=extraction_usage,
            )
            logger.info("JSON extraction successful")
        except PromptInjectionError as e:
            logger.warning(f"Prompt injection detected in CV {filename}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "ARCHIVO_RECHAZADO_SEGURIDAD: "
                    "El documento contiene instrucciones maliciosas embebidas. "
                    "Si crees que es un error, convierte el CV a texto plano (.txt) e inténtalo de nuevo."
                ),
            )
        except LLMRateLimitError as e:
            # Cuota del proveedor cloud agotada (visto con Groq: 12k tokens/min).
            # Fallar claro > guardar datos corruptos del fallback regex.
            logger.warning(f"LLM rate limit durante extracción de {filename}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "El sistema de análisis está saturado en este momento. "
                    "Espera un minuto y vuelve a subir este CV."
                ),
            )
        except Exception as e:
            logger.error(f"LLM extraction error for {filename}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al procesar el CV con IA. Intenta de nuevo en unos momentos."
            )
        
        # Create candidate in database.
        # ``summary`` ahora se llena con el ``resumen_profesional`` extraído del CV
        # (antes quedaba en ``None`` y el embedding `summary` se construía con un
        # texto sintético muy pobre — perdíamos la auto-presentación del candidato).
        candidate_db = CandidateDB(
            full_name=extracted.datos_personales.nombre_completo,
            email=extracted.datos_personales.email,
            phone=extracted.datos_personales.telefono,
            linkedin=extracted.datos_personales.linkedin,
            github=extracted.datos_personales.github,
            summary=extracted.resumen_profesional,
            skills=extracted.habilidades or [],
            raw_text=raw_text,
            file_path=filename,
            file_hash=file_hash,
            status="new",
            job_id=job_id,
            idiomas=[
                {
                    "idioma": id.idioma,
                    "nivel": id.nivel,
                    "certificacion": id.certificacion,
                }
                for id in (extracted.idiomas or [])
                if id.idioma
            ],
        )
        
        # Save file to MinIO
        try:
            db.add(candidate_db)
            await db.flush()  # get the ID before commit
            storage.upload_cv(
                candidate_id=str(candidate_db.id),
                file_bytes=content,
                filename=filename,
                # Tipo derivado de la extensión validada, NO el que declaró el
                # cliente (evita almacenar un content-type malicioso).
                content_type=_safe_media_type(filename),
            )
            logger.info(f"CV saved to MinIO for candidate {candidate_db.id}")
        except Exception as e:
            logger.warning(f"Could not save CV to MinIO: {e}")
        
        if candidate_db not in db.new:
            db.add(candidate_db)
        await db.commit()
        await db.refresh(candidate_db)
        
        # Add experience entries
        exp_dbs: list[ExperienceEntryDB] = []
        for exp in extracted.experiencia_profesional or []:
            start_d = parse_date_str(exp.fecha_inicio)
            _CURRENT_MARKERS = {
                'presente', 'actual', 'actualidad', 'current',
                'a la fecha', 'hasta hoy', 'hasta la fecha', 'en curso', 'hoy', '–', '-',
            }
            fecha_fin_lower = (exp.fecha_fin or '').strip().lower()
            is_current = (
                exp.es_trabajo_actual or
                fecha_fin_lower in _CURRENT_MARKERS
            )
            end_d = None if is_current else parse_date_str(exp.fecha_fin)

            # Fallback: parse 'periodo' when the LLM filled that field but left
            # fecha_inicio / fecha_fin as null (fallback parser for any model).
            # periodo examples: "Enero 2025 – Actualidad", "Junio 2024 – Septiembre 2024"
            if exp.periodo and (not start_d or (not is_current and not end_d)):
                pparts = _re.split(r'\s*[–—]\s*', exp.periodo.strip(), maxsplit=1)
                if pparts and not start_d:
                    start_d = parse_date_str(pparts[0])
                if len(pparts) >= 2 and not is_current:
                    end_str = pparts[1].strip()
                    if end_str.lower() in _CURRENT_MARKERS:
                        is_current = True
                    elif not end_d:
                        end_d = parse_date_str(end_str)
                        if end_d:
                            is_current = False
            # Build description: only include "Periodo:" line if the text is meaningful
            periodo_text = (exp.periodo or "").strip()
            logros_text = "\n".join(exp.resumen_logros or [])
            if periodo_text:
                description_text = f"Periodo: {periodo_text}\n{logros_text}"
            else:
                # Fallback: build human-readable period from dates
                start_label = exp.fecha_inicio or ""
                end_label = exp.fecha_fin or ("Presente" if is_current else "")
                if start_label or end_label:
                    description_text = f"Periodo: {start_label} - {end_label}\n{logros_text}"
                else:
                    description_text = logros_text
            exp_db = ExperienceEntryDB(
                candidate_id=candidate_db.id,
                company=exp.empresa,
                title=exp.cargo,
                start_date=start_d,
                end_date=end_d,
                description=description_text,
                is_current=is_current,
            )
            db.add(exp_db)
            exp_dbs.append(exp_db)

        # Save education entries.
        # ``end_date`` se construye preferentemente de ``edu.fecha_fin`` (formato
        # YYYY-MM tras normalización); ``anio_egreso`` queda como fallback legacy.
        # ``degree_status`` (Titulado/Bachiller/En curso/Colegiado/...) se persiste
        # para que el recruiter pueda filtrar candidatos por progreso del grado.
        for edu in extracted.educacion or []:
            edu_start = parse_date_str(edu.fecha_inicio)
            edu_end = parse_date_str(edu.fecha_fin)
            if not edu_end and edu.anio_egreso and edu.anio_egreso.isdigit():
                try:
                    edu_end = date_type(int(edu.anio_egreso), 12, 31)
                except ValueError:
                    pass
            edu_db = EducationEntryDB(
                candidate_id=candidate_db.id,
                institution=edu.institucion,
                degree=edu.titulo,
                education_type=getattr(edu, "tipo", "educacion") or "educacion",
                degree_status=getattr(edu, "estatus", None),
                start_date=edu_start,
                end_date=edu_end,
            )
            db.add(edu_db)
        
        await db.commit()
        
        # Generate embeddings and index in Qdrant
        # Build natural-language texts per dimension — richer than plain lists
        experience_parts = [
            f"{exp.cargo} en {exp.empresa}: {' '.join(exp.resumen_logros)}"
            for exp in (extracted.experiencia_profesional or [])
        ]
        experience_text = (
            f"Experiencia profesional: {'. '.join(experience_parts)}"
            if experience_parts else ""
        )

        education_parts = [
            f"{edu.titulo} en {edu.institucion}" + (f" ({edu.anio_egreso})" if edu.anio_egreso else "")
            for edu in (extracted.educacion or [])
        ]
        education_text = (
            f"Formación académica: {'. '.join(education_parts)}"
            if education_parts else ""
        )

        top_skills = extracted.habilidades[:15] if extracted.habilidades else []
        skills_text = (
            f"Habilidades y tecnologías: {', '.join(top_skills)}"
            if top_skills else ""
        )

        # ``summary_text``: texto que se vectoriza como vector "summary" en Qdrant.
        # Antes se construía sintéticamente con nombre + cargo + skills, lo cual
        # producía un embedding muy pobre porque todos los CVs lucían igual.
        # Ahora se prefiere el ``resumen_profesional`` real del CV (auto-presentación
        # del candidato), enriquecido con datos clave para el matching semántico.
        first_title = (
            extracted.experiencia_profesional[0].cargo
            if extracted.experiencia_profesional
            else ""
        )
        nombre = extracted.datos_personales.nombre_completo
        if extracted.resumen_profesional:
            summary_text = (
                f"Candidato: {nombre}. "
                + (f"Rol actual: {first_title}. " if first_title else "")
                + f"Perfil profesional: {extracted.resumen_profesional}"
            )
        else:
            summary_text = (
                f"Candidato: {nombre}. "
                + (f"Rol actual: {first_title}. " if first_title else "")
                + (
                    f"Habilidades principales: {', '.join(top_skills[:5])}."
                    if top_skills
                    else ""
                )
            )

        vectors = await embedder.embed_candidate_aspects(
            experience_text=experience_text,
            education_text=education_text,
            skills_text=skills_text,
            summary_text=summary_text,
        )
        
        # Años de experiencia para el payload de Qdrant. Reutiliza la MISMA
        # función que la lista/ficha (calculate_experience_years): fusiona
        # intervalos solapados (no cuenta doble los empleos concurrentes) y
        # respeta el is_current ya resuelto al insertar las filas (que incluye
        # 'En curso', 'a la fecha', etc.). Antes un bucle inline distinto usaba
        # un set de marcadores reducido e inflaba/subestimaba los años, dando un
        # número en la búsqueda y otro en la ficha del mismo candidato.
        experience_years_calc = calculate_experience_years(exp_dbs)

        await qdrant.upsert_candidate(
            candidate_id=candidate_db.id,
            vectors=vectors,
            payload={
                "full_name": candidate_db.full_name,
                "skills": candidate_db.skills,
                "experience_years": experience_years_calc,
                "status": candidate_db.status,
                "job_id": str(job_id) if job_id else None,
            }
        )

        # LPDP: entrada de PII al sistema. Registra qué reclutador subió qué CV
        # y para qué vacante. La IP queda disponible para reconstruir el origen
        # ante una solicitud ARCO-P.
        await audit.log_access(
            user_id=str(current_user.id),
            action="cv_uploaded",
            resource_type="candidate",
            resource_id=str(candidate_db.id),
            ip_address=request.client.host if request.client else None,
            details={
                "filename": filename,
                "job_id": str(job_id) if job_id else None,
                "file_hash": file_hash[:16],  # prefijo, no completo (no es secreto pero evita ruido)
            },
        )

        # Consumo del LLM en la extracción (tokens reales + latencia + tiempo de
        # lectura del documento). Alimenta KPIs de costo/tiempo por CV en
        # /admin/usage. Nunca rompe el upload (el recorder hace try/except).
        await recorder.record(
            operation="extract_cv",
            usage=extraction_usage,
            candidate_id=candidate_db.id,
            job_id=job_id,
            user_id=str(current_user.id),
            preprocess_ms=preprocess_ms,
        )

        return UploadResponse(
            id=candidate_db.id,
            filename=filename,
            status="processed",
            extracted_name=candidate_db.full_name,
            skills_count=len(candidate_db.skills),
            message="CV processed and indexed successfully",
            job_id=job_id,
        )

    except HTTPException:
        # Don't swallow our own deliberate rejections (security blocks, prompt
        # injection, missing job_id, …) — they already carry the precise reason
        # the recruiter needs to act on.
        await db.rollback()
        raise
    except Exception as e:
        logger.exception(f"Failed to process CV {filename}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "No pudimos procesar este CV por un error interno. "
                "Verificá que el archivo no esté dañado y volvé a subirlo. "
                "Si el problema persiste, revisá los logs del backend."
            ),
        )


@router.get("", response_model=CandidateListResponse)
async def list_candidates(
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    job_id_filter: Optional[UUID] = Query(None, alias="job_id"),
):
    """List candidates with pagination. Optionally filter by job_id or status."""
    query = select(CandidateDB).options(selectinload(CandidateDB.experience))

    if status_filter:
        query = query.where(CandidateDB.status == status_filter)
    if job_id_filter:
        query = query.where(CandidateDB.job_id == job_id_filter)

    # Efficient count with same filters
    count_query = select(func.count(CandidateDB.id))
    if status_filter:
        count_query = count_query.where(CandidateDB.status == status_filter)
    if job_id_filter:
        count_query = count_query.where(CandidateDB.job_id == job_id_filter)
    total = (await db.execute(count_query)).scalar_one()

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
                phone=c.phone,
                linkedin=c.linkedin,
                github=c.github,
                summary=c.summary,
                skills=c.skills or [],
                total_experience_years=calculate_experience_years(c.experience),
                status=c.status,
                job_id=c.job_id,
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
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed candidate information from PostgreSQL."""
    # Single round-trip with eager-loaded experience+education.
    # Previous version made 3 sequential SELECTs which doubled p95 latency
    # for the candidate detail page.
    result = await db.execute(
        select(CandidateDB)
        .options(
            selectinload(CandidateDB.experience),
            selectinload(CandidateDB.education),
        )
        .where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )

    experience = candidate.experience or []
    education = candidate.education or []

    # Audit log: register who accessed this candidate's data (LPDP compliance).
    # Runs after the data fetch so a slow audit insert never blocks the response
    # (commits on the same db session, but the SELECTs are already done).
    await AuditLogger(db_session=db).log_access(
        user_id=str(current_user.id),
        action="view",
        resource_type="candidate",
        resource_id=str(candidate_id),
    )

    return CandidateDetailResponse(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        linkedin=candidate.linkedin,
        github=candidate.github,
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
                "is_current": e.is_current,
                "description": e.description,
            }
            for e in experience
        ],
        education=[
            {
                "institution": e.institution,
                "degree": e.degree,
                "field_of_study": e.field_of_study,
                "education_type": getattr(e, "education_type", "educacion") or "educacion",
                "degree_status": getattr(e, "degree_status", None),
                "start_date": str(e.start_date) if e.start_date else None,
                "end_date": str(e.end_date) if e.end_date else None,
            }
            for e in education
        ],
        idiomas=candidate.idiomas or [],
        raw_text=candidate.raw_text,
    )


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: UUID,
    request: Request,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    audit: AuditLogger = Depends(get_audit_logger),
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
    storage: StorageService = Depends(get_storage),
):
    """Delete a candidate (Admin only).

    LPDP — derecho de cancelación (ARCO-P): borra el candidato de la DB
    relacional, los vectores en Qdrant y el archivo original en MinIO. La
    eliminación queda registrada en ``audit_logs`` para poder demostrar a la
    ANPD que la solicitud fue atendida.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar")
    result = await db.execute(
        select(CandidateDB).where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )

    # Snapshot del nombre antes de borrar — el log debe sobrevivir al delete.
    candidate_name_snapshot = candidate.full_name
    candidate_email_snapshot = candidate.email

    # Remove from vector store
    await qdrant.delete_candidate(candidate_id)

    # Remove from MinIO
    try:
        storage.delete_cv(str(candidate_id))
    except Exception as e:
        logger.warning(f"Could not delete CV from MinIO: {e}")

    # Remove from database
    await db.delete(candidate)
    await db.commit()

    # LPDP: log de cancelación (derecho al olvido). Persistir DESPUÉS del
    # commit para evitar romper la transacción si el insert del audit falla.
    await audit.log_access(
        user_id=str(current_user.id),
        action="candidate_deleted",
        resource_type="candidate",
        resource_id=str(candidate_id),
        ip_address=request.client.host if request.client else None,
        details={
            "candidate_name": candidate_name_snapshot,
            "candidate_email": candidate_email_snapshot,
        },
    )


@router.get("/{candidate_id}/download")
async def download_cv(
    candidate_id: UUID,
    request: Request,
    current_user: UserResponse = Depends(get_current_active_user),
    audit: AuditLogger = Depends(get_audit_logger),
    storage: StorageService = Depends(get_storage),
):
    """Download the original CV file."""
    try:
        file_bytes, content_type, filename = storage.download_cv(str(candidate_id))
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV file not found. The file may have been uploaded before file storage was enabled."
        )

    # LPDP: acceso al CV original (documento con PII completa). Loguear ANTES
    # de devolver la respuesta.
    await audit.log_access(
        user_id=str(current_user.id),
        action="cv_downloaded",
        resource_type="candidate",
        resource_id=str(candidate_id),
        ip_address=request.client.host if request.client else None,
        details={"filename": filename},
    )

    # Tipo seguro derivado de la extensión (no el guardado, que en subidas
    # antiguas pudo haber venido del cliente) + nosniff. La descarga ya va como
    # attachment, así que el navegador no la ejecuta.
    return Response(
        content=file_bytes,
        media_type=_safe_media_type(filename),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{candidate_id}/preview")
async def preview_cv(
    candidate_id: UUID,
    current_user: UserResponse = Depends(get_current_active_user),
    storage: StorageService = Depends(get_storage),
):
    """Preview the CV file inline (opens in browser tab for PDFs).

    Seguridad: se sirve con un Content-Type derivado de la extensión validada
    (no el que declaró quien subió el archivo) y con ``nosniff``. Solo los PDF
    se muestran inline; cualquier otro tipo se fuerza a descarga (attachment)
    para que el navegador nunca lo renderice como HTML/script.
    """
    try:
        file_bytes, _stored_type, filename = storage.download_cv(str(candidate_id))
        media_type = _safe_media_type(filename)
        # Inline solo si es PDF (los navegadores no previsualizan DOCX de todas
        # formas); el resto se descarga para no ejecutarlo en el origen.
        disposition = "inline" if media_type == "application/pdf" else "attachment"
        return Response(
            content=file_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f'{disposition}; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV file not found. The file may have been uploaded before file storage was enabled."
        )


class StatusUpdateRequest(BaseModel):
    status: str


class CandidatePersonalUpdateRequest(BaseModel):
    """Editable contact fields when LLM extraction missed or mis-read them."""
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None


class ExperienceEntryInput(BaseModel):
    """One job entry as it travels in/out of the experience editor."""
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None  # "YYYY-MM" or "YYYY-MM-DD"
    end_date: Optional[str] = None    # "YYYY-MM", null, or end-marker
    is_current: bool = False
    description: Optional[str] = None


class ExperienceListUpdateRequest(BaseModel):
    """Full replacement of a candidate's professional experience.

    The frontend sends the whole list; the backend deletes the old rows and
    inserts the new ones. This avoids per-row id tracking and makes the UI
    safe to "undo" mid-edit (changes only persist on save).
    """
    entries: List[ExperienceEntryInput]


@router.patch("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate_personal_data(
    candidate_id: UUID,
    update: CandidatePersonalUpdateRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
):
    """Update candidate personal/contact data manually.

    Used when the LLM extraction misses email/phone/linkedin/name. Only fields
    explicitly sent in the request body are updated; empty strings are stored
    as null. The full_name change also propagates to the Qdrant payload so
    semantic search and matching keep showing the corrected name.
    """
    result = await db.execute(
        select(CandidateDB)
        .options(selectinload(CandidateDB.experience))
        .where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    payload = update.model_dump(exclude_unset=True)
    name_changed = False
    for field, value in payload.items():
        clean = value.strip() if isinstance(value, str) else value
        if clean == "":
            clean = None
        if field == "full_name":
            if not clean:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="full_name cannot be empty",
                )
            name_changed = clean != candidate.full_name
        setattr(candidate, field, clean)

    await db.commit()
    await db.refresh(candidate)

    if name_changed:
        try:
            qdrant.client.set_payload(
                collection_name=qdrant.COLLECTION_NAME,
                payload={"full_name": candidate.full_name},
                points=[str(candidate_id)],
            )
        except Exception as exc:
            logger.warning(f"Could not sync full_name to Qdrant for {candidate_id}: {exc}")

    return CandidateResponse(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        linkedin=candidate.linkedin,
        github=candidate.github,
        summary=candidate.summary,
        skills=candidate.skills or [],
        total_experience_years=calculate_experience_years(candidate.experience or []),
        status=candidate.status,
        job_id=candidate.job_id,
    )


@router.put("/{candidate_id}/experience", response_model=CandidateDetailResponse)
async def replace_candidate_experience(
    candidate_id: UUID,
    payload: ExperienceListUpdateRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    """Replace the candidate's experience list and recompute derived state.

    Editing experience cascades into three places:
    - PostgreSQL ``experience_entries`` rows (full replacement, not partial).
    - The ``experience_years`` payload field in Qdrant (used for ranking).
    - The ``experience`` named vector in Qdrant (so semantic match reflects the
      corrected job titles, companies and descriptions).

    ``total_experience_years`` is not stored — it is derived from the rows on
    every read via :func:`calculate_experience_years`, so the corrected number
    surfaces automatically in subsequent GETs.
    """
    result = await db.execute(
        select(CandidateDB)
        .options(
            selectinload(CandidateDB.experience),
            selectinload(CandidateDB.education),
        )
        .where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    # Build the new ORM rows up-front so a parsing error rolls back cleanly.
    new_rows: List[ExperienceEntryDB] = []
    for idx, entry in enumerate(payload.entries):
        title = (entry.title or "").strip() or None
        company = (entry.company or "").strip() or None
        description = (entry.description or "").strip() or None
        if not title and not company:
            # Skip blank rows the user may have left while editing.
            continue

        start = parse_date_str(entry.start_date)
        end = None if entry.is_current else parse_date_str(entry.end_date)
        if start and end and end < start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Entrada {idx + 1}: la fecha fin no puede ser anterior a la de inicio",
            )

        new_rows.append(ExperienceEntryDB(
            candidate_id=candidate.id,
            title=title,
            company=company,
            start_date=start,
            end_date=end,
            is_current=bool(entry.is_current),
            description=description,
        ))

    # Replace the list — delete-then-insert keeps row ids stable-by-recreation,
    # which is fine because the UI never references them across edits.
    for old in list(candidate.experience or []):
        await db.delete(old)
    for row in new_rows:
        db.add(row)
    await db.commit()
    await db.refresh(candidate, attribute_names=["experience"])

    # Recompute derived experience years for the Qdrant payload + response.
    experience = candidate.experience or []
    total_years = calculate_experience_years(experience)

    # Resync the ``experience`` vector so semantic matching reflects the edit.
    # Build the same kind of text as on upload: "Cargo en Empresa: descripción".
    experience_parts = []
    for exp in experience:
        line = f"{exp.title or ''} en {exp.company or ''}".strip(" en ")
        if exp.description:
            line = f"{line}: {exp.description}" if line else exp.description
        if line:
            experience_parts.append(line)
    experience_text = (
        f"Experiencia profesional: {'. '.join(experience_parts)}"
        if experience_parts else ""
    )

    try:
        new_vector = await embedder.embed_text(experience_text)
        # Update the named vector in-place + bump the experience_years payload.
        from qdrant_client.http import models as _qm
        qdrant.client.update_vectors(
            collection_name=qdrant.COLLECTION_NAME,
            points=[_qm.PointVectors(id=str(candidate_id), vector={"experience": new_vector})],
        )
        qdrant.client.set_payload(
            collection_name=qdrant.COLLECTION_NAME,
            payload={"experience_years": total_years},
            points=[str(candidate_id)],
        )
    except Exception as exc:
        # Don't fail the edit if Qdrant is briefly unavailable — the DB is the
        # source of truth and the next reindex will repair the vector.
        logger.warning(f"Could not sync Qdrant experience for {candidate_id}: {exc}")

    education = candidate.education or []
    return CandidateDetailResponse(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        linkedin=candidate.linkedin,
        github=candidate.github,
        summary=candidate.summary,
        skills=candidate.skills or [],
        total_experience_years=total_years,
        status=candidate.status,
        experience=[
            {
                "company": e.company,
                "title": e.title,
                "start_date": str(e.start_date) if e.start_date else None,
                "end_date": str(e.end_date) if e.end_date else None,
                "is_current": e.is_current,
                "description": e.description,
            }
            for e in experience
        ],
        education=[
            {
                "institution": e.institution,
                "degree": e.degree,
                "field_of_study": e.field_of_study,
                "education_type": getattr(e, "education_type", "educacion") or "educacion",
                "degree_status": getattr(e, "degree_status", None),
                "start_date": str(e.start_date) if e.start_date else None,
                "end_date": str(e.end_date) if e.end_date else None,
            }
            for e in education
        ],
        idiomas=candidate.idiomas or [],
        raw_text=candidate.raw_text,
    )


@router.patch("/{candidate_id}/status")
async def update_candidate_status(
    candidate_id: UUID,
    status_update: StatusUpdateRequest,
    request: Request,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    audit: AuditLogger = Depends(get_audit_logger),
):
    """Update candidate status in PostgreSQL.

    DS 115-2025-PCM: este es el momento donde el reclutador toma la decisión
    final (intervención humana) sobre un candidato — `hired`, `rejected`, etc.
    El cambio queda registrado en ``audit_logs`` con el estado previo y el
    nuevo, identificando al reclutador. Permite reconstruir ante una solicitud
    ARCO-P o una inspección de la ANPD quién tomó cada decisión.
    """
    result = await db.execute(
        select(CandidateDB).where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )

    # Validate status value
    valid_statuses = ["new", "screening", "shortlisted", "interview", "offer", "hired", "rejected"]
    new_status = status_update.status.lower()

    # Map Spanish names to English if needed
    status_mapping = {
        "nuevo": "new",
        "revisado": "screening",
        "reviewed": "screening",
        "preseleccionado": "shortlisted",
        "en entrevista": "interview",
        "entrevista": "interview",
        "oferta": "offer",
        "contratado": "hired",
        "rechazado": "rejected"
    }

    if new_status in status_mapping:
        new_status = status_mapping[new_status]

    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    previous_status = candidate.status
    candidate.status = new_status
    await db.commit()

    # LPDP + DS 115: registro de la decisión humana sobre el candidato.
    # Especial relevancia cuando se pasa a "hired" o "rejected" — son las
    # decisiones que tienen impacto material en la persona.
    await audit.log_access(
        user_id=str(current_user.id),
        action="candidate_status_changed",
        resource_type="candidate",
        resource_id=str(candidate_id),
        ip_address=request.client.host if request.client else None,
        details={
            "candidate_name": candidate.full_name,
            "previous_status": previous_status,
            "new_status": new_status,
            "is_final_decision": new_status in ("hired", "rejected"),
        },
    )

    return {"id": str(candidate_id), "status": new_status}



