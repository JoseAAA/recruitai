"""
SQLAlchemy ORM Models for RecruitAI
Maps to PostgreSQL tables defined in init-db.sql
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, Date, Float, ForeignKey, Integer, String, Text, TIMESTAMP, ARRAY, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class CandidateDB(Base):
    """Candidate model - maps to candidates table."""
    __tablename__ = "candidates"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    linkedin: Mapped[Optional[str]] = mapped_column(String(500))
    github: Mapped[Optional[str]] = mapped_column(String(500))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    skills: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    file_hash: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="new")
    rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5 stars
    job_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("job_profiles.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    idiomas: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    experience: Mapped[List["ExperienceEntryDB"]] = relationship("ExperienceEntryDB", back_populates="candidate", cascade="all, delete-orphan")
    education: Mapped[List["EducationEntryDB"]] = relationship("EducationEntryDB", back_populates="candidate", cascade="all, delete-orphan")
    notes: Mapped[List["CandidateNoteDB"]] = relationship("CandidateNoteDB", back_populates="candidate", cascade="all, delete-orphan")
    job: Mapped[Optional["JobProfileDB"]] = relationship("JobProfileDB", back_populates="candidates")


class ExperienceEntryDB(Base):
    """Experience entry model."""
    __tablename__ = "experience_entries"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"))
    company: Mapped[Optional[str]] = mapped_column(String(255))
    title: Mapped[Optional[str]] = mapped_column(String(255))
    start_date: Mapped[Optional[datetime]] = mapped_column(Date)
    end_date: Mapped[Optional[datetime]] = mapped_column(Date)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationship
    candidate: Mapped["CandidateDB"] = relationship("CandidateDB", back_populates="experience")


class EducationEntryDB(Base):
    """Education entry model.

    ``degree_status``: progreso del grado (Titulado, Bachiller, Egresado,
    En curso, Cursando, Culminado, Colegiado, Inconcluso). Crítico en Perú
    para roles regulados — un Ingeniero "Bachiller" no firma planos; uno
    "Colegiado" sí. Permite filtros del tipo "MBA Titulado" vs "MBA en curso".
    """

    __tablename__ = "education_entries"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE")
    )
    institution: Mapped[Optional[str]] = mapped_column(String(255))
    degree: Mapped[Optional[str]] = mapped_column(String(255))
    field_of_study: Mapped[Optional[str]] = mapped_column(String(255))
    # "educacion" o "certificacion"
    education_type: Mapped[Optional[str]] = mapped_column(String(50), default="educacion")
    degree_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(Date)
    end_date: Mapped[Optional[datetime]] = mapped_column(Date)
    gpa: Mapped[Optional[str]] = mapped_column(String(10))

    # Relationship
    candidate: Mapped["CandidateDB"] = relationship(
        "CandidateDB", back_populates="education"
    )


class JobProfileDB(Base):
    """Job profile model - maps to job_profiles table."""
    __tablename__ = "job_profiles"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    required_skills: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    preferred_skills: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    responsibilities: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    key_objectives: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    seniority_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    work_modality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    min_experience_years: Mapped[int] = mapped_column(Integer, default=0)
    education_level: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="active")
    scoring_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    required_languages: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    candidates: Mapped[List["CandidateDB"]] = relationship("CandidateDB", back_populates="job", passive_deletes=True)


class AuditLogDB(Base):
    """Audit log for LPDP Perú compliance — persisted to PostgreSQL."""
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    user_id: Mapped[Optional[str]] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[str] = mapped_column(String(255))
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    details: Mapped[Optional[dict]] = mapped_column(JSON)


class UserDB(Base):
    """User model for authentication."""
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="recruiter")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class CandidateNoteDB(Base):
    """Candidate notes for HR tracking."""
    __tablename__ = "candidate_notes"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"))
    user_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    note_type: Mapped[str] = mapped_column(String(50), default="general")  # general, interview, feedback, status_change
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5 stars
    previous_status: Mapped[Optional[str]] = mapped_column(String(20))
    new_status: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    candidate: Mapped["CandidateDB"] = relationship("CandidateDB", back_populates="notes")
    user: Mapped[Optional["UserDB"]] = relationship("UserDB")


class CloudConnectionDB(Base):
    """Cloud storage connection with encrypted OAuth tokens."""
    __tablename__ = "cloud_connections"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "onedrive" | "google_drive"
    folder_path: Mapped[Optional[str]] = mapped_column(String(500))  # Watched folder path
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    last_sync: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    user: Mapped["UserDB"] = relationship("UserDB")


class MatchResultDB(Base):
    """Persisted AI match scores for candidate-job pairs (maps to match_results table)."""
    __tablename__ = "match_results"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("job_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_name: Mapped[Optional[str]] = mapped_column(String(255))
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    experience_score: Mapped[Optional[float]] = mapped_column(Float)
    education_score: Mapped[Optional[float]] = mapped_column(Float)
    skills_score: Mapped[Optional[float]] = mapped_column(Float)
    relevant_experience_years: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(String(50))
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    missing_skills: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    bonus_skills: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    guia_entrevista: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    scored_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class LLMUsageDB(Base):
    """Registro de consumo del LLM por operación — base de KPIs/OKRs y costeo.

    Cada llamada al LLM (extracción de CV, matching, explicación al candidato,
    análisis de vacante) deja aquí una fila con los **tokens reales** que
    reportó la API del proveedor y la **latencia** medida en el servidor. Sirve
    para responder preguntas de negocio: ¿cuánto cuesta procesar un CV?, ¿cuánto
    tarda un análisis IA?, ¿qué proveedor conviene?

    Diseño "write-only / analytics" igual que ``audit_logs``:
    - ``candidate_id`` / ``job_id`` son UUID nullable **sin** ForeignKey, para
      que borrar un candidato o una vacante nunca elimine el historial de
      consumo ni falle por una constraint. La trazabilidad de costos sobrevive
      a los derechos ARCO-P.
    - Las filas no se editan ni se borran (salvo retención por LPDP).

    Indexado por ``operation``, ``provider`` y ``created_at`` para que las
    agregaciones del panel ``/admin/usage`` sean baratas.
    """
    __tablename__ = "llm_usage"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), index=True
    )
    # extract_cv | match | explain | extract_job
    operation: Mapped[str] = mapped_column(String(20), index=True)
    # ollama | openai | gemini | groq
    provider: Mapped[str] = mapped_column(String(20), index=True)
    model: Mapped[Optional[str]] = mapped_column(String(80))

    # Tokens reales devueltos por la API del proveedor (None si no los reportó).
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer)

    # Latencia de la llamada al LLM (wall-clock, incluye reintentos del proveedor).
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    # Tiempo de pre-procesado del documento antes del LLM (solo extract_cv):
    # leer el PDF/DOCX y convertirlo a Markdown. Permite el KPI "tiempo total
    # de procesar un CV" = preprocess_ms + latency_ms.
    preprocess_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Contexto de negocio (nullable, sin FK — ver docstring).
    candidate_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), index=True)
    job_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(255))
    # Agrupa todas las filas de una misma ejecución de matching (N candidatos).
    batch_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), index=True)

    # ¿La llamada al LLM tuvo éxito? success=False registra fallos (cuota
    # agotada, timeouts) para medir la tasa de error sin inflar el costo.
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(80))


class SystemSettingDB(Base):
    """
    System settings stored in database.

    SECURITY NOTE:
    - API keys and secrets are NOT stored here (they stay in .env)
    - Only non-sensitive configuration (provider selection, model names, paths)
    """
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
