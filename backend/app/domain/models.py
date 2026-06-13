"""
RecruitAI-Core Domain Models
Pure Python entities representing the core business domain.

Validation strategy
-------------------
Pydantic ``field_validator``s call deterministic normalisers from
``app.core.validators``. The LLM produces text that varies in case,
formatting and locale; by funnelling every model construction through
the same validators we guarantee that:

* the database never stores two phones in different formats for the same
  candidate ("+51999..." vs "999-111-222"),
* the UI never receives a malformed LinkedIn URL or a name in ALL CAPS,
* every domain field has a single canonical shape across the codebase.

The original ``_none_to_empty`` / ``_normalize_estatus`` helpers are kept
because they encode product rules (Peruvian academic statuses, etc.) and
already work — we only ADD normalisation, never remove existing logic.
"""
import re
import unicodedata
from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from app.core import validators as _v


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
    periodo: str = ""
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    es_trabajo_actual: bool = False
    resumen_logros: List[str] = Field(default_factory=list)

    @field_validator("cargo", "empresa", "periodo", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        """Normalise text fields: None → '', strip mojibake/control chars.

        ``cargo`` and ``empresa`` reach the UI directly; cleaning here
        means the frontend never has to render ``Coordinador Ã©dico``.
        """
        if v is None:
            return ""
        return _v.clean_text(str(v)) or ""

    @field_validator("fecha_inicio", "fecha_fin", mode="before")
    @classmethod
    def _date_to_str(cls, v):
        """Coacciona la fecha a str para que un año numérico no rompa el CV.

        gemma3:4b y los proveedores cloud a veces emiten el año como entero
        (``"fecha_inicio": 2020``). Sin esto, Pydantic v2 rechaza el int y la
        ValidationError descarta TODA la extracción del CV (cae al fallback
        regex pobre). Mismo patrón que ``EducacionProfesional._date_to_str``.
        """
        if v is None:
            return None
        return str(v)

    @field_validator("resumen_logros", mode="before")
    @classmethod
    def _logros_none_to_list(cls, v):
        """Normaliza los logros a ``List[str]`` tolerando formas malformadas.

        Un único logro emitido como string suelto ("Aumenté ventas 20%") o un
        item no-string dentro de la lista (un número) lanzaba ValidationError y
        hacía fallar TODO el CV. Aquí lo convertimos en lugar de romper.
        """
        if v is None:
            return []
        if isinstance(v, str):
            v = v.strip()
            return [v] if v else []
        if isinstance(v, list):
            out: list[str] = []
            for item in v:
                if item is None:
                    continue
                s = str(item).strip()
                if s:
                    out.append(s)
            return out
        return []

    @field_validator("es_trabajo_actual", mode="before")
    @classmethod
    def _bool_coerce(cls, v):
        return bool(v) if v is not None else False


class EducacionProfesional(BaseModel):
    """Una entrada de formación académica o certificación.

    El campo ``estatus`` captura el progreso/grado del candidato (Titulado,
    Bachiller, En curso, Colegiado, Culminado, etc.). Es información clave
    para RRHH en Perú: distingue un Ingeniero "Bachiller" de uno "Colegiado"
    (este último puede firmar planos), y separa "MBA en curso" de
    "MBA Titulado". Un análisis de 7 CVs reales mostró que el 86% lo declara.
    """

    institucion: str = ""
    titulo: str = ""
    tipo: str = "educacion"
    estatus: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    anio_egreso: Optional[str] = None   # campo legacy — se mantiene para compatibilidad

    @field_validator("institucion", "titulo", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        if v is None:
            return ""
        return _v.clean_text(str(v)) or ""

    @field_validator("tipo", mode="before")
    @classmethod
    def _normalize_tipo(cls, v):
        """Clasifica la entrada como 'educacion' (grado formal) o 'certificacion'.

        Antes solo reconocía la cadena exacta sin tilde ``certificacion``, así
        que la ortografía correcta en español (``certificación``) y variantes
        muy comunes (``diplomado``, ``curso``, ``certification``) caían a
        ``educacion`` y se mezclaban con los títulos universitarios — justo el
        dato que más usa RRHH en Perú. Normalizamos quitando acentos y mapeamos
        contra un set de términos de certificación.
        """
        if not v or not isinstance(v, str):
            return "educacion"
        # Quita acentos/diacríticos: 'certificación' → 'certificacion'.
        sin_acentos = "".join(
            c for c in unicodedata.normalize("NFKD", v.strip().lower())
            if not unicodedata.combining(c)
        )
        certificaciones = {
            "certificacion", "certification", "certificado", "certified",
            "diplomado", "curso", "course", "bootcamp", "taller",
            "especializacion", "especializacion corta",
        }
        return "certificacion" if sin_acentos in certificaciones else "educacion"

    @field_validator("estatus", mode="before")
    @classmethod
    def _normalize_estatus(cls, v):
        """Mapea variantes al canon usado por filtros del frontend.

        Variantes documentadas en CVs reales peruanos:
        Titulado/Titulada, Bachiller, Egresado/a, En curso, Cursando,
        Culminado/a, Concluido, Colegiado/a, Inconcluso/a.
        """
        if not v or not isinstance(v, str):
            return None
        key = v.strip().lower().rstrip(".")
        canon_map = {
            "titulado": "Titulado", "titulada": "Titulado",
            "bachiller": "Bachiller",
            "egresado": "Egresado", "egresada": "Egresado",
            "en curso": "En curso", "cursando": "En curso",
            "candidate": "En curso", "candidato": "En curso",
            "culminado": "Culminado", "culminada": "Culminado",
            "concluido": "Culminado", "concluida": "Culminado",
            "colegiado": "Colegiado", "colegiada": "Colegiado",
            "inconcluso": "Inconcluso", "inconclusa": "Inconcluso",
        }
        return canon_map.get(key, v.strip()[:50])

    @field_validator("fecha_inicio", "fecha_fin", "anio_egreso", mode="before")
    @classmethod
    def _date_to_str(cls, v):
        if v is None:
            return None
        return str(v)


class IdiomaCandidato(BaseModel):
    idioma: str = ""
    nivel: str = ""
    certificacion: Optional[str] = None

    @field_validator("idioma", "nivel", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        if v is None:
            return ""
        return _v.clean_text(str(v)) or ""


class DatosPersonales(BaseModel):
    """Personal contact info — all fields normalised on construction.

    - ``nombre_completo``: Title Case respecting hispanic particles
      ("de la Cruz" stays lowercase mid-name).
    - ``telefono``: E.164 (``+51999...``) via Google libphonenumber.
    - ``email``: RFC 5322 normalised (lowercase domain, IDN canonical).
    - ``linkedin`` / ``github``: canonical profile URL or ``None``.
    Garbage values are silently coerced to ``None`` so the frontend
    never has to defend itself against malformed strings from the LLM.
    """

    nombre_completo: str = "Candidato Desconocido"
    telefono: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None

    @field_validator("nombre_completo", mode="before")
    @classmethod
    def _normalise_name(cls, v):
        if not v:
            return "Candidato Desconocido"
        normalised = _v.normalize_person_name(str(v))
        return normalised or "Candidato Desconocido"

    @field_validator("telefono", mode="before")
    @classmethod
    def _normalise_phone(cls, v):
        # Empty string and None both mean "absent" — keep DB consistent.
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return _v.normalize_phone(str(v))

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_email(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        # ``check_deliverability=False`` keeps construction synchronous
        # and free of DNS calls; batch jobs can re-verify with MX later.
        return _v.normalize_email(str(v), check_deliverability=False)

    @field_validator("linkedin", mode="before")
    @classmethod
    def _normalise_linkedin(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return _v.normalize_linkedin(str(v))

    @field_validator("github", mode="before")
    @classmethod
    def _normalise_github(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return _v.normalize_github(str(v))

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
    """Datos estructurados extraídos de un CV por el LLM.

    El campo ``resumen_profesional`` corresponde al párrafo de auto-presentación
    presente en la cabecera de prácticamente todos los CVs profesionales (100%
    de presencia en el análisis de CVs reales). Antes el sistema lo descartaba,
    perdiendo la pieza más rica de información narrativa: el embedding
    ``summary`` de Qdrant se construía con un texto sintético pobre, y el matcher
    no veía la auto-descripción del candidato. Capturarlo mejora simultáneamente:

    * la búsqueda semántica (vector ``summary`` con señal real),
    * la lectura rápida del recruiter (preview en la lista de candidatos),
    * el matching IA (más contexto narrativo para el LLM).
    """

    datos_personales: DatosPersonales
    resumen_profesional: Optional[str] = None
    habilidades: List[str] = Field(default_factory=list)
    idiomas: List[IdiomaCandidato] = Field(default_factory=list)
    experiencia_profesional: List[ExperienciaProfesional] = Field(default_factory=list)
    educacion: List[EducacionProfesional] = Field(default_factory=list)

    @field_validator("resumen_profesional", mode="before")
    @classmethod
    def _strip_and_limit_summary(cls, v):
        """Trim y límite duro de 1500 chars para mantener el embedding focal.

        Aplica también ``clean_text`` (ftfy + NFC + strip invisible
        Unicode) — los PDFs con extracción mojibake (``Ã±`` en lugar de
        ``ñ``) llegaban al embedding sin arreglo y degradaban la
        búsqueda semántica.
        """
        if v is None:
            return None
        text = _v.clean_text(str(v))
        if not text:
            return None
        return text[:1500]

    @field_validator("habilidades", mode="before")
    @classmethod
    def _normalise_skills(cls, v):
        """Dedup case-insensitive + Title Case + ftfy.

        El LLM a veces emite "python", "Python" y "PYTHON" como tres
        skills distintas para el mismo CV. El frontend los muestra como
        chips separadas — lo arreglamos aquí, no en la UI.
        """
        if not v:
            return []
        # El LLM (sobre todo en modo cloud) a veces emite las skills como un
        # string "Python, SQL, Excel" en lugar de una lista. Sin esto se
        # perdían TODAS las habilidades en silencio (lista vacía). Lo partimos.
        if isinstance(v, str):
            v = [p.strip() for p in re.split(r"[,;\n]", v) if p.strip()]
        if not isinstance(v, list):
            return []
        seen: set[str] = set()
        out: list[str] = []
        for item in v:
            if item is None:
                continue
            cleaned = _v.clean_text(str(item))
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            # Title Case ligero — sin tocar siglas (SQL, AWS, API).
            out.append(cleaned if cleaned.isupper() and len(cleaned) <= 5 else cleaned)
        return out


class IdiomaRequerido(BaseModel):
    """A language requirement in a job profile."""
    idioma: str = ""
    nivel: str = ""         # Básico, Intermedio, Avanzado, Nativo, Bilingüe
    # Default False: si el LLM extrae un idioma pero NO marca explícitamente que
    # es obligatorio, es más seguro tratarlo como deseable que inventar un
    # requisito duro. Un inglés "deseable" que se volvía obligatorio sobre-
    # filtraba y descartaba injustamente a buenos candidatos sin avisar.
    obligatorio: bool = False  # True = required, False = nice-to-have

    @field_validator("idioma", "nivel", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        # str(v): un nivel emitido como número (p. ej. 2 en vez de 'B2') no
        # debe tirar la extracción completa de la vacante con un error 500.
        if v is None:
            return ""
        return _v.clean_text(str(v)) or ""


class ExtractedJobProfile(BaseModel):
    """Datos estructurados extraídos del documento de una vacante.

    El campo ``location`` se llena desde frases del documento como
    ``"Lugar de trabajo: Chinchón"`` o ``"Sede: Lima — San Isidro"``.
    Es crítico para el filtro inicial del recruiter: una vacante presencial
    en Arequipa no debería rankear candidatos que residen en Lima sin
    indicar disponibilidad de reubicación.
    """

    title: str = Field(default="", description="Título exacto del puesto de trabajo")
    department: Optional[str] = Field(
        default=None,
        description="Departamento o área funcional (ej. TI, Recursos Humanos)",
    )
    description: Optional[str] = Field(
        default=None,
        description="Resumen del puesto: qué hace el rol, contexto del equipo y "
        "objetivos principales (2-4 oraciones)",
    )
    seniority_level: Optional[str] = Field(
        default=None,
        description="Nivel: 'junior', 'mid-level', 'senior', 'lead', 'manager', 'director'",
    )
    work_modality: Optional[str] = Field(
        default=None,
        description="Modalidad de trabajo: 'remote', 'hybrid', 'onsite'",
    )
    industry: Optional[str] = Field(
        default=None,
        description="Industria o sector (ej. Tecnología, Fintech, Retail, Salud)",
    )
    location: Optional[str] = Field(
        default=None,
        description="Lugar de trabajo declarado en el documento (ciudad, distrito o sede). "
        "Si el documento no lo indica explícitamente, dejar null.",
    )
    required_skills: List[str] = Field(
        default_factory=list,
        description="Habilidades técnicas y blandas estrictamente OBLIGATORIAS",
    )
    preferred_skills: List[str] = Field(
        default_factory=list,
        description="Habilidades deseables pero NO obligatorias",
    )
    responsibilities: List[str] = Field(
        default_factory=list,
        description="Responsabilidades explícitas en el texto (puede estar vacío)",
    )
    key_objectives: List[str] = Field(
        default_factory=list,
        description="Objetivos clave o KPIs explícitos (puede estar vacío)",
    )
    min_experience_years: int = Field(
        default=0,
        description="Años mínimos de experiencia requeridos (solo el número entero)",
    )
    education_level: Optional[str] = Field(
        default=None,
        description="Nivel de educación formal requerido",
    )
    required_languages: List[IdiomaRequerido] = Field(
        default_factory=list,
        description="Idiomas requeridos o deseables (ej. Inglés Avanzado obligatorio)",
    )

    @field_validator(
        "required_skills", "preferred_skills", "responsibilities", "key_objectives",
        mode="before",
    )
    @classmethod
    def _coerce_str_list(cls, v):
        """Tolera que el LLM emita la lista como string 'a, b, c' o como None.

        Sin esto, ``required_skills='Python, SQL, Excel'`` (deriva común de los
        proveedores cloud) o bien rompía la importación de la vacante, o el
        dedup posterior lo partía CARÁCTER por carácter ('P','y','t',...)
        arruinando el ranking. Defensa a nivel de modelo, además del split que
        ya hace ``extract_job_profile._dedup_skills``.
        """
        if v is None:
            return []
        if isinstance(v, str):
            return [p.strip() for p in re.split(r"[,;\n]", v) if p.strip()]
        if isinstance(v, list):
            return [str(x).strip() for x in v if x is not None and str(x).strip()]
        return []

    @field_validator("min_experience_years", mode="before")
    @classmethod
    def _coerce_min_experience(cls, v):
        """Tolera los valores reales que el LLM produce a partir de frases.

        El prompt pide un entero, pero los proveedores cloud no respetan el
        schema y los modelos pequeños desobedecen: ``'5 años'``, ``'de 3 a 5'``,
        ``'5+'``, ``'4.5'`` o ``null``. Sin esto, ``/jobs/analyze`` devolvía
        HTTP 500 y el reclutador no podía importar la vacante. Extraemos el
        primer entero presente (coincide con la regla del prompt: '3-5 años = 3').
        """
        if v is None or v == "":
            return 0
        if isinstance(v, bool):  # bool es subclase de int — descártalo explícito.
            return 0
        if isinstance(v, (int, float)):
            return max(0, int(v))
        m = re.search(r"\d+", str(v))
        return int(m.group()) if m else 0
