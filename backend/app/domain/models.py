"""
RecruitAI-Core Domain Models
Pure Python entities representing the core business domain.
"""
from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


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

class ExperienciaProfesional(BaseModel):
    cargo: str = ""
    empresa: str = ""
    periodo: str = ""  # keep for context
    fecha_inicio: Optional[str] = None  # format: "YYYY-MM" e.g. "2021-12"
    fecha_fin: Optional[str] = None     # format: "YYYY-MM" or "Presente"
    es_trabajo_actual: bool = False
    resumen_logros: List[str] = Field(default_factory=list)


class EducacionProfesional(BaseModel):
    institucion: str = ""
    titulo: str = ""
    anio_egreso: Optional[str] = None  # e.g. "2019"
    tipo: str = "educacion"  # "educacion" (universidad, maestria, doctorado, instituto) or "certificacion" (bootcamp, curso, especialización)


class DatosPersonales(BaseModel):
    nombre_completo: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None

# (Manteniendo ExperienceEntry y EducationEntry originales solo para CandidateDB para no romper el resto del sistema, pero no se usan para el prompt LLM ahora)
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


class ScoringDimension(BaseModel):
    """A single scoring dimension with its weight."""
    dimension: str
    weight: float = Field(ge=0, le=1)
    description: Optional[str] = None


DEFAULT_SCORING_CONFIG: List[ScoringDimension] = [
    ScoringDimension(dimension="skills", weight=0.40, description="Skills técnicos y blandos"),
    ScoringDimension(dimension="experience", weight=0.35, description="Experiencia laboral relevante"),
    ScoringDimension(dimension="education", weight=0.25, description="Formación académica"),
]


class ScoreBreakdown(BaseModel):
    """Detailed score breakdown for explainability — dynamic weights per job."""
    scores: dict = Field(default_factory=dict)   # {"skills": 85.0, "experience": 70.0, ...}
    weights: dict = Field(default_factory=dict)  # {"skills": 0.40, "experience": 0.35, ...}

    # Legacy fields — kept for backwards compatibility with existing frontend
    skills_score: float = Field(default=0.0, ge=0, le=100)
    experience_score: float = Field(default=0.0, ge=0, le=100)
    education_score: float = Field(default=0.0, ge=0, le=100)

    @property
    def overall_score(self) -> float:
        """Weighted average using dynamic weights when available, otherwise legacy formula."""
        if self.scores and self.weights:
            return sum(self.scores.get(d, 0) * w for d, w in self.weights.items())
        # Legacy fallback
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


class ExtractedResume(BaseModel):
    """Schema for LLM-extracted resume data, EXACTLY matching user's Spanish template"""
    datos_personales: DatosPersonales
    habilidades: List[str] = Field(default_factory=list)
    experiencia_profesional: List[ExperienciaProfesional] = Field(default_factory=list)
    educacion: List[EducacionProfesional] = Field(default_factory=list)


class ExtractedJobProfile(BaseModel):
    """Schema for LLM-extracted job description data"""
    title: str = Field(default="", description="Título exacto del puesto de trabajo")
    department: Optional[str] = Field(default=None, description="Departamento o área funcional (ej. TI, Recursos Humanos)")
    description: Optional[str] = Field(default=None, description="Resumen del puesto: qué hace el rol, contexto del equipo y objetivos principales (2-4 oraciones)")
    seniority_level: Optional[str] = Field(default=None, description="Nivel de seniority: 'junior', 'mid-level', 'senior', 'lead', 'manager', 'director'")
    work_modality: Optional[str] = Field(default=None, description="Modalidad de trabajo: 'remote', 'hybrid', 'onsite'")
    industry: Optional[str] = Field(default=None, description="Industria o sector de la empresa (ej. Tecnología, Fintech, Retail, Salud)")
    required_skills: List[str] = Field(default_factory=list, description="Lista de habilidades técnicas y blandas estrictamente OBLIGATORIAS")
    preferred_skills: List[str] = Field(default_factory=list, description="Lista de habilidades deseables pero NO obligatorias")
    responsibilities: List[str] = Field(default_factory=list, description="Lista de responsabilidades y tareas principales del puesto (5-10 items)")
    key_objectives: List[str] = Field(default_factory=list, description="Objetivos clave o KPIs que el puesto debe lograr en los primeros 6-12 meses (3-5 items)")
    min_experience_years: int = Field(default=0, description="Años mínimos de experiencia requeridos (solo el número)")
    education_level: Optional[str] = Field(default=None, description="Nivel de educación formal requerido")
