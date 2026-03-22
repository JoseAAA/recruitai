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
    """Education entry model."""
    __tablename__ = "education_entries"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"))
    institution: Mapped[Optional[str]] = mapped_column(String(255))
    degree: Mapped[Optional[str]] = mapped_column(String(255))
    field_of_study: Mapped[Optional[str]] = mapped_column(String(255))
    education_type: Mapped[Optional[str]] = mapped_column(String(50), default="educacion")  # "educacion" or "certificacion"
    start_date: Mapped[Optional[datetime]] = mapped_column(Date)
    end_date: Mapped[Optional[datetime]] = mapped_column(Date)
    gpa: Mapped[Optional[str]] = mapped_column(String(10))

    # Relationship
    candidate: Mapped["CandidateDB"] = relationship("CandidateDB", back_populates="education")


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
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    candidates: Mapped[List["CandidateDB"]] = relationship("CandidateDB", back_populates="job")


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
