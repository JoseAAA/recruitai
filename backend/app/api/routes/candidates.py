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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi.responses import Response

from app.adapters import EmbeddingService, LLMEngine, QdrantRepository
from app.adapters.storage import StorageService, BUCKET_CVS
from app.core.privacy import AuditLogger
from app.adapters.document_extractor import DocumentExtractor, DocumentParsingError
from app.api.routes.auth import get_current_active_user, UserResponse
from app.core.database import get_db
from app.core.config import settings
from app.core.rate_limit import limit
from app.db.models import CandidateDB, ExperienceEntryDB, EducationEntryDB
from app.domain import CandidateStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["Candidates"])


# ============ Date Parsing Helpers ============

SPANISH_MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
    'noviembre': 11, 'diciembre': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


def parse_date_str(s: Optional[str]) -> Optional[date_type]:
    """Parse date strings like '2021-12', 'DICIEMBRE 2021', 'Mayo 2024' into a date object."""
    if not s or s.strip().lower() in ('presente', 'actual', 'current', 'actualidad', ''):
        return None
    s = s.strip()
    # Try YYYY-MM
    m = _re.match(r'^(\d{4})-(\d{1,2})$', s)
    if m:
        return date_type(int(m.group(1)), int(m.group(2)), 1)
    # Try "MONTH YYYY" or "YYYY MONTH"
    parts = s.lower().split()
    year = next((int(p) for p in parts if p.isdigit() and len(p) == 4), None)
    month = next((SPANISH_MONTHS[p] for p in parts if p in SPANISH_MONTHS), None)
    if year and month:
        return date_type(year, month, 1)
    # Try just YYYY
    if s.isdigit() and len(s) == 4:
        return date_type(int(s), 1, 1)
    return None


# ============ Request/Response Schemas ============

class CandidateResponse(BaseModel):
    id: UUID
    full_name: str
    email: Optional[str]
    phone: Optional[str] = None
    linkedin: Optional[str] = None
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


# ============ Dependencies ============

def get_docling_extractor() -> DocumentExtractor:
    return DocumentExtractor()


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


def get_llm_engine() -> LLMEngine:
    return LLMEngine()


def get_qdrant_repo() -> QdrantRepository:
    return QdrantRepository()


def get_storage() -> StorageService:
    return StorageService()


# ============ Helper Functions ============

def calculate_experience_years(experience_entries: List[ExperienceEntryDB]) -> float:
    """Calculate total years of experience."""
    from datetime import date as date_type
    today = date_type.today()
    total_years = 0.0
    for exp in experience_entries:
        if exp.start_date:
            # For current jobs use today as end date
            end = today if (exp.is_current or not exp.end_date) else exp.end_date
            years = (end.year - exp.start_date.year) + (end.month - exp.start_date.month) / 12
            total_years += max(0, years)
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
    allowed_types = [".pdf", ".docx"]
    filename = file.filename or "unknown"
    
    file_ext = "." + filename.lower().split(".")[-1] if "." in filename else ""
    
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {allowed_types}"
        )
    
    try:
        # Read file content
        content = await file.read()
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
        
        # 1. Convert to Markdown using Docling
        try:
            logger.info(f"Starting Docling extraction for {filename}")
            markdown_content, _ = await docling.parse_bytes(content, filename)
            raw_text = markdown_content
            logger.info(f"Docling extraction successful. Markdown length: {len(raw_text)}")
        except Exception as e:
            logger.error(f"Docling extraction failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse document: {str(e)}"
            )
            
        # 2. Extract JSON using LLM (Gemma3)
        try:
            logger.info(f"Starting LLM extraction for {filename}")
            extracted = await llm.extract_resume(raw_text, filename=filename)
            logger.info("JSON extraction successful")
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to extract structured data: {str(e)}"
            )
        
        # Create candidate in database
        candidate_db = CandidateDB(
            full_name=extracted.datos_personales.nombre_completo,
            email=extracted.datos_personales.email,
            phone=extracted.datos_personales.telefono,
            linkedin=extracted.datos_personales.linkedin,
            summary=None,
            skills=extracted.habilidades or [],
            raw_text=raw_text,
            file_path=filename,
            file_hash=file_hash,
            status="new",
            job_id=job_id,
        )
        
        # Save file to MinIO
        try:
            db.add(candidate_db)
            await db.flush()  # get the ID before commit
            storage.upload_cv(
                candidate_id=str(candidate_db.id),
                file_bytes=content,
                filename=filename,
                content_type=file.content_type or "application/octet-stream",
            )
            logger.info(f"CV saved to MinIO for candidate {candidate_db.id}")
        except Exception as e:
            logger.warning(f"Could not save CV to MinIO: {e}")
        
        if candidate_db not in db.new:
            db.add(candidate_db)
        await db.commit()
        await db.refresh(candidate_db)
        
        # Add experience entries
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
            # fecha_inicio / fecha_fin as null (common with small models like gemma3:4b).
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

        # Save education entries
        for edu in extracted.educacion or []:
            end_year = None
            if edu.anio_egreso and edu.anio_egreso.isdigit():
                try:
                    end_year = date_type(int(edu.anio_egreso), 12, 31)
                except ValueError:
                    pass
            edu_db = EducationEntryDB(
                candidate_id=candidate_db.id,
                institution=edu.institucion,
                degree=edu.titulo,
                education_type=getattr(edu, 'tipo', 'educacion') or 'educacion',
                end_date=end_year,
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

        first_title = extracted.experiencia_profesional[0].cargo if extracted.experiencia_profesional else ""
        summary_text = (
            f"Candidato: {extracted.datos_personales.nombre_completo}. "
            + (f"Rol actual: {first_title}. " if first_title else "")
            + (f"Habilidades principales: {', '.join(top_skills[:5])}." if top_skills else "")
        )

        vectors = await embedder.embed_candidate_aspects(
            experience_text=experience_text,
            education_text=education_text,
            skills_text=skills_text,
            summary_text=summary_text,
        )
        
        await qdrant.upsert_candidate(
            candidate_id=candidate_db.id,
            vectors=vectors,
            payload={
                "full_name": candidate_db.full_name,
                "skills": candidate_db.skills,
                "experience_years": 0,
                "status": candidate_db.status,
                "job_id": str(job_id) if job_id else None,
            }
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
        
    except Exception as e:
        logger.error(f"Failed to process CV {filename}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process CV: {str(e)}"
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
    query = select(CandidateDB)

    if status_filter:
        query = query.where(CandidateDB.status == status_filter)
    if job_id_filter:
        query = query.where(CandidateDB.job_id == job_id_filter)

    # Get total count with same filters
    count_query = select(CandidateDB.id)
    if status_filter:
        count_query = count_query.where(CandidateDB.status == status_filter)
    if job_id_filter:
        count_query = count_query.where(CandidateDB.job_id == job_id_filter)
    count_result = await db.execute(count_query)
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
                phone=c.phone,
                linkedin=c.linkedin,
                summary=c.summary,
                skills=c.skills or [],
                total_experience_years=0,
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
    result = await db.execute(
        select(CandidateDB).where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )

    # Audit log: register who accessed this candidate's data (LPDP compliance)
    await AuditLogger(db_session=db).log_access(
        user_id=str(current_user.id),
        action="view",
        resource_type="candidate",
        resource_id=str(candidate_id),
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
        phone=candidate.phone,
        linkedin=candidate.linkedin,
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
                "education_type": getattr(e, 'education_type', 'educacion') or 'educacion',
            }
            for e in education
        ],
        raw_text=candidate.raw_text,
    )


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: UUID,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    qdrant: QdrantRepository = Depends(get_qdrant_repo),
    storage: StorageService = Depends(get_storage),
):
    """Delete a candidate (Admin only)."""
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


@router.get("/{candidate_id}/download")
async def download_cv(
    candidate_id: UUID,
    current_user: UserResponse = Depends(get_current_active_user),
    storage: StorageService = Depends(get_storage),
):
    """Download the original CV file."""
    try:
        file_bytes, content_type, filename = storage.download_cv(str(candidate_id))
        return Response(
            content=file_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV file not found. The file may have been uploaded before file storage was enabled."
        )


@router.get("/{candidate_id}/preview")
async def preview_cv(
    candidate_id: UUID,
    current_user: UserResponse = Depends(get_current_active_user),
    storage: StorageService = Depends(get_storage),
):
    """Preview the CV file inline (opens in browser tab for PDFs)."""
    try:
        file_bytes, content_type, filename = storage.download_cv(str(candidate_id))
        return Response(
            content=file_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
            },
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV file not found. The file may have been uploaded before file storage was enabled."
        )


class StatusUpdateRequest(BaseModel):
    status: str


@router.patch("/{candidate_id}/status")
async def update_candidate_status(
    candidate_id: UUID,
    status_update: StatusUpdateRequest,
    current_user: UserResponse = Depends(get_current_active_user),
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
    
    candidate.status = new_status
    await db.commit()
    
    return {"id": str(candidate_id), "status": new_status}


# ============ Notes Endpoints ============

class NoteRequest(BaseModel):
    content: str
    note_type: str = "general"


@router.post("/{candidate_id}/notes")
async def add_candidate_note(
    candidate_id: UUID,
    note: NoteRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a note to a candidate."""
    # Check candidate exists
    result = await db.execute(
        select(CandidateDB).where(CandidateDB.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    # For now, store notes in a simple format
    # In a real app, you'd have a separate Notes table
    from datetime import datetime
    
    note_entry = {
        "type": note.note_type,
        "content": note.content,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    # Append to existing notes (stored as JSON in summary for now)
    # TODO: Create proper CandidateNote table
    if candidate.summary:
        candidate.summary += f"\n\n[{note.note_type.upper()}] {note.content}"
    else:
        candidate.summary = f"[{note.note_type.upper()}] {note.content}"
    
    await db.commit()
    
    return {"id": str(candidate_id), "note": note_entry, "message": "Note added"}

