"""
RecruitAI-Core Domain Models
Pure Python entities representing the core business domain.
"""
from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CandidateStatus(str, Enum):
    NEW = "new"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"


class JobStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class EducationLevel(str, Enum):
    HIGH_SCHOOL = "high_school"
    ASSOCIATE = "associate"
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"
    OTHER = "other"


# ============ Experience & Education Entries ============

class ExperienceEntry(BaseModel):
    """Work experience entry extracted from CV"""
    company: str
    title: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None
    is_current: bool = False
    
    @property
    def duration_months(self) -> int:
        """Calculate duration in months"""
        if not self.start_date:
            return 0
        end = self.end_date or date.today()
        return (end.year - self.start_date.year) * 12 + (end.month - self.start_date.month)


class EducationEntry(BaseModel):
    """Education entry extracted from CV"""
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    gpa: Optional[str] = None


# ============ Core Entities ============

class Candidate(BaseModel):
    """Core Candidate entity"""
    id: UUID = Field(default_factory=uuid4)
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    education: List[EducationEntry] = Field(default_factory=list)
    raw_text: Optional[str] = None
    file_path: Optional[str] = None
    file_hash: Optional[str] = None
    status: CandidateStatus = CandidateStatus.NEW
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def total_experience_years(self) -> float:
        """Calculate total years of experience"""
        total_months = sum(exp.duration_months for exp in self.experience)
        return round(total_months / 12, 1)
    
    @property
    def highest_education(self) -> Optional[str]:
        """Get highest education level"""
        if not self.education:
            return None
        # Simple heuristic: return the most recent degree
        return self.education[0].degree if self.education else None


class JobProfile(BaseModel):
    """Job Profile / Vacancy entity"""
    id: UUID = Field(default_factory=uuid4)
    title: str
    department: Optional[str] = None
    description: Optional[str] = None
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    min_experience_years: int = 0
    education_level: Optional[EducationLevel] = None
    status: JobStatus = JobStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScoreBreakdown(BaseModel):
    """Detailed score breakdown for explainability"""
    experience_score: float = Field(ge=0, le=100)
    education_score: float = Field(ge=0, le=100)
    skills_score: float = Field(ge=0, le=100)
    
    @property
    def overall_score(self) -> float:
        """Weighted average of component scores"""
        # Weights: Skills 40%, Experience 35%, Education 25%
        return (
            self.skills_score * 0.40 +
            self.experience_score * 0.35 +
            self.education_score * 0.25
        )


class MatchResult(BaseModel):
    """Result of matching a candidate against a job profile"""
    id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    job_id: UUID
    scores: ScoreBreakdown
    explanation: str = ""
    missing_skills: List[str] = Field(default_factory=list)
    bonus_skills: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def overall_score(self) -> float:
        return self.scores.overall_score


# ============ LLM Extraction Schemas ============

class ExtractedResume(BaseModel):
    """Schema for LLM-extracted resume data"""
    full_name: str = Field(description="Full name of the candidate")
    email: Optional[str] = Field(default=None, description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    summary: Optional[str] = Field(default=None, description="Professional summary or objective")
    skills: List[str] = Field(default_factory=list, description="List of technical and soft skills")
    experience: List[ExperienceEntry] = Field(default_factory=list, description="Work experience entries")
    education: List[EducationEntry] = Field(default_factory=list, description="Education history")


class ExtractedJobProfile(BaseModel):
    """Schema for LLM-extracted job description data"""
    title: str = Field(description="Job title")
    department: Optional[str] = Field(default=None, description="Department or team")
    required_skills: List[str] = Field(default_factory=list, description="Required skills")
    preferred_skills: List[str] = Field(default_factory=list, description="Nice-to-have skills")
    min_experience_years: int = Field(default=0, description="Minimum years of experience required")
    education_level: Optional[str] = Field(default=None, description="Required education level")
