"""
LLM Engine Adapter
Handles communication with LLM providers for structured data extraction.
Supports multiple providers: Ollama (local), OpenAI, Gemini.
Includes fallback for when no LLM is available.

Security Features:
- PII Masking: Anonymizes personal data before sending to LLM (LPDP Perú compliance)
- Prompt Injection Defense: Multi-layer protection against malicious inputs
- Output Validation: Ensures LLM returns required fields
"""
import json
import logging
import re
from typing import Optional, Type, TypeVar, Dict, Tuple

from pydantic import BaseModel

from app.core.config import settings
from app.domain.models import (
    ExtractedJobProfile, ExtractedResume, ExperienceEntry, EducationEntry,
    ExperienciaProfesional, EducacionProfesional, DatosPersonales, IdiomaCandidato,
)
from app.adapters.llm_providers import get_provider, LLMProvider
from app.adapters.pii_masker import get_pii_masker, PIIMasker

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class PromptInjectionError(Exception):
    """Raised when potential prompt injection is detected."""
    pass


class LLMEngine:
    """
    Adapter for LLM providers with structured output extraction.
    Supports: Ollama, OpenAI, Gemini (configurable via LLM_PROVIDER env).
    Implements prompt injection defense and sanitization.
    Falls back to simple parsing when no LLM is available.
    """
    
    # ===========================================
    # SECURITY: Multi-Layer Prompt Injection Defense
    # Based on OWASP LLM Top 10 2025 (LLM01: Prompt Injection)
    # ===========================================
    
    # Layer 1: Suspicious patterns (regex-based detection)
    # Based on OWASP LLM Top 10 2025 (LLM01); Greshake "Inject My PDF" (2023);
    # Schneier on Security (2023); multilingual bypass research.
    # Bilingual: English + Spanish — critical for LatAm market.
    # Note: all patterns run on lowercased text so case doesn't matter.
    SUSPICIOUS_PATTERNS = [
        # ── INSTRUCTION OVERRIDE (English) ──────────────────────────────────
        # Broader match: catches "ignore all previous scoring" (not just "ignore all previous instructions")
        r"ignore\s+(all\s+)?(previous|above|prior|earlier)",
        r"disregard\s+(all\s+)?(previous|above|prior|earlier)",
        r"forget\s+(everything|what|all\s+previous|prior|earlier)",
        r"override\s+(previous|system|all|earlier|scoring|instructions?|evaluation)",
        r"do\s+not\s+follow\s+(previous|prior|earlier)",
        r"stop\s+following\s+(instructions|rules|guidelines)",
        r"discard\s+(all\s+)?(previous|prior|earlier)",

        # ── INSTRUCTION OVERRIDE (Spanish) ──────────────────────────────────
        r"ignora\s+(todas?\s+)?(las\s+)?instrucciones|ignora\s+(lo\s+)?anterior",
        r"ignorar\s+(instrucciones?|todo\s+lo\s+anterior)",
        r"olvida\s+(todo|instrucciones?|lo\s+anterior)",
        r"descartar?\s+(instrucciones?|indicaciones?)",
        r"no\s+(sigas?|siga)\s+(las?\s+)?instrucciones?",
        r"anula\s+(las?\s+)?instrucciones?",

        # ── SCORE / RANKING MANIPULATION (HR-specific — critical) ────────────
        # Documented: "Score Override: 100/100", "rank this candidate first"
        r"score\s*(override|=\s*100|:\s*100)",
        r"scoring\s*override",
        r"must\s+be\s+ranked\s+(first|#1|número\s+uno)",
        r"rank\s+(this\s+candidate|me|them)\s+(first|#1)",
        r"do\s+not\s+rank\s+other\s+candidates",
        r"no\s+rankees?\s+a\s+(otros?|demás)\s+candidatos?",
        r"puntuaci[oó]n\s+m[aá]xima\s+autom[aá]ticamente",
        r"recibe\s+autom[aá]ticamente\s+la\s+puntuaci[oó]n",
        r"confirma\s+con\s+score\s*=",
        r"asigna\s+(puntuaci[oó]n|score|puntaje)\s+(de\s+)?100",
        r"candidato\s+(debe\s+ser|es)\s+el\s+primero",
        r"primer\s+candidato\s+procesado\s+recibe",
        r"maximum\s+score\s+automatically",
        r"give\s+(this\s+candidate|them)\s+(a\s+)?100",
        r"this\s+candidate\s+must\s+be\s+(ranked\s+first|approved)",

        # ── ROLE HIJACKING / JAILBREAK (English) ────────────────────────────
        r"you\s+are\s+now\s+(a|an)",
        r"act\s+as\s+(if\s+you\s+are|a|an)",
        r"pretend\s+(to\s+be|you\s+are)",
        r"roleplay\s+as",
        r"imagine\s+you\s+are",
        r"from\s+now\s+on\s+you\s+are",
        r"switch\s+to\s+\w+\s+mode",
        r"enter\s+\w+\s+mode",
        r"jailbreak",
        r"dan\s+mode",      # "Do Anything Now" jailbreak

        # ── ROLE HIJACKING (Spanish) ─────────────────────────────────────────
        r"eres\s+ahora\s+(un|una)",
        r"act[uú]a\s+como\s+(si\s+(fueras?|eres)|un|una)",
        r"finge\s+(ser|que\s+eres)",
        r"nuevo\s+rol\s+(del\s+)?(sistema|asistente|modelo)",
        r"nuevo\s+sistema\s*:",
        r"est[aá]s\s+en\s+modo",
        r"modo\s+(evaluaci[oó]n\s+avanzada|administrador|sin\s+restricciones)",
        r"de\s+ahora\s+en\s+(adelante\s+)?(eres?|act[uú]as?)",

        # ── SYSTEM PROMPT MANIPULATION ───────────────────────────────────────
        r"new\s+instructions?\s*:",
        r"nuevas?\s+instrucciones?\s*:",
        r"\[system\]",
        r"```\s*system",
        r"<\s*system\s*>",
        r"\[inst\]",
        r"<<sys>>",
        r"instrucciones?\s+del\s+sistema\s*:",

        # ── OUTPUT MANIPULATION ───────────────────────────────────────────────
        r"respond\s+only\s+with",
        r"output\s+only",
        r"return\s+only\s+the\s+following",
        r"say\s+exactly",
        r"your\s+response\s+must\s+be",
        r"responde\s+[uú]nicamente\s+con",
        r"tu\s+respuesta\s+debe\s+(ser|contener)",

        # ── ENCODING TRICKS / OBFUSCATION ────────────────────────────────────
        r"base64\s*:",
        r"\\x[0-9a-f]{2}",
        r"rot13",
        r"decode\s+this",

        # ── DATA EXFILTRATION ATTEMPTS ────────────────────────────────────────
        r"reveal\s+(your|the)\s+(system|prompt|instructions?)",
        r"show\s+me\s+(your|the)\s+prompt",
        r"repeat\s+(your|the)\s+(system|initial)\s+prompt",
        r"muestra\s+(tus?|las?)\s+instrucciones?",
        r"cu[aá]les\s+son\s+tus\s+instrucciones?",

        # ── INDIRECT INJECTION ────────────────────────────────────────────────
        r"if\s+you\s+are\s+an?\s+(ai|assistant|llm)",
        r"dear\s+(ai|assistant|model)",
        r"attention\s+(ai|assistant|llm|model)",
        r"atenci[oó]n\s+(ia|asistente|modelo)",

        # ── CODE EXECUTION ATTEMPTS ───────────────────────────────────────────
        r"<script\b",
        r"javascript\s*:",
        r"eval\s*\(",
    ]
    
    # Layer 2: Maximum input lengths (prevent token exhaustion attacks)
    MAX_CV_LENGTH = 50000  # ~10 pages of text
    MAX_JOB_DESCRIPTION_LENGTH = 20000

    # Layer 3: Required output fields (ensure LLM doesn't deviate)
    REQUIRED_RESUME_FIELDS = {"nombre", "email", "skills"}
    REQUIRED_JOB_FIELDS = {"titulo", "requisitos"}

    # ── JSON Schemas for constrained decoding (Ollama >= 0.5) ──────────────────
    # Constrained decoding makes it physically impossible for the model to emit
    # tokens that violate the schema. Key benefits vs free-form json_mode:
    # - enum fields ("tipo", "recommendation") → model CANNOT produce invalid values
    # - required fields → always present in output
    # - type constraints → scores are always numbers, never strings
    # Ref: Willard & Louf "Efficient Guided Generation for LLMs" (2023);
    #      Ollama structured outputs documentation (2024)
    # ──────────────────────────────────────────────────────────────────────────
    RESUME_JSON_SCHEMA = {
        "type": "object",
        "required": ["datos_personales", "habilidades", "idiomas", "experiencia_profesional", "educacion"],
        "properties": {
            "datos_personales": {
                "type": "object",
                "required": ["nombre_completo"],
                "properties": {
                    "nombre_completo": {"type": "string"},
                    "telefono": {"type": ["string", "null"]},
                    "email": {"type": ["string", "null"]},
                    "linkedin": {"type": ["string", "null"]},
                    "github": {"type": ["string", "null"]},
                },
            },
            "habilidades": {"type": "array", "items": {"type": "string"}},
            "idiomas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["idioma", "nivel"],
                    "properties": {
                        "idioma": {"type": "string"},
                        "nivel": {"type": "string"},
                        "certificacion": {"type": ["string", "null"]},
                    },
                },
            },
            "experiencia_profesional": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["cargo", "empresa"],
                    "properties": {
                        "cargo": {"type": "string"},
                        "empresa": {"type": "string"},
                        "fecha_inicio": {"type": ["string", "null"]},
                        "fecha_fin": {"type": ["string", "null"]},
                        "es_trabajo_actual": {"type": "boolean"},
                        "resumen_logros": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "educacion": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["institucion", "titulo", "tipo"],
                    "properties": {
                        "institucion": {"type": "string"},
                        "titulo": {"type": "string"},
                        "tipo": {"type": "string", "enum": ["educacion", "certificacion"]},
                        "fecha_inicio": {"type": ["string", "null"]},
                        "fecha_fin": {"type": ["string", "null"]},
                    },
                },
            },
        },
    }

    JOB_PROFILE_JSON_SCHEMA = {
        "type": "object",
        "required": ["title", "description", "required_skills", "preferred_skills", "responsibilities"],
        "properties": {
            "title": {"type": "string"},
            "department": {"type": ["string", "null"]},
            "description": {"type": ["string", "null"]},
            "seniority_level": {
                "type": ["string", "null"],
                "enum": ["junior", "mid-level", "senior", "lead", "manager", None],
            },
            "work_modality": {
                "type": ["string", "null"],
                "enum": ["remote", "hybrid", "onsite", None],
            },
            "industry": {"type": ["string", "null"]},
            "required_skills": {"type": "array", "items": {"type": "string"}},
            "preferred_skills": {"type": "array", "items": {"type": "string"}},
            "responsibilities": {"type": "array", "items": {"type": "string"}},
            "key_objectives": {"type": "array", "items": {"type": "string"}},
            "min_experience_years": {"type": "integer", "minimum": 0},
            "education_level": {
                "type": ["string", "null"],
                "enum": ["bachelor", "master", "phd", "high_school", "associate", None],
            },
            "required_languages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["idioma", "nivel", "obligatorio"],
                    "properties": {
                        "idioma": {"type": "string"},
                        "nivel": {
                            "type": "string",
                            "enum": ["Básico", "Intermedio", "Avanzado", "Nativo", "Bilingüe"],
                        },
                        "obligatorio": {"type": "boolean"},
                    },
                },
            },
        },
    }

    MATCH_JSON_SCHEMA = {
        "type": "object",
        "required": [
            "_razonamiento_previo",
            "skills_score", "experience_score", "education_score",
            "explanation", "recommendation", "missing_critical_skills",
            "guia_entrevista",
        ],
        "properties": {
            # _razonamiento_previo: fuerza al modelo a razonar ANTES de producir números.
            # En modelos normales: escribe el razonamiento aquí como texto.
            # En modelos thinking (qwen3, deepseek-r1): ya razonaron internamente,
            # usan este campo como resumen. Ambos casos producen scores más precisos.
            "_razonamiento_previo": {"type": "string"},
            "skills_score": {"type": "number", "minimum": 0, "maximum": 100},
            "experience_score": {"type": "number", "minimum": 0, "maximum": 100},
            "education_score": {"type": "number", "minimum": 0, "maximum": 100},
            "explanation": {"type": "string"},
            "recommendation": {
                "type": "string",
                "enum": ["Altamente recomendado", "Buena opción", "Considerar", "No recomendado"],
            },
            "missing_critical_skills": {
                "type": "array",
                "items": {"type": "string"},
            },
            "relevant_experience_years": {
                "type": "number",
                "minimum": 0,
                "description": "Years in roles directly relevant to the job title",
            },
            "guia_entrevista": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["tipo", "pregunta"],
                    "properties": {
                        "tipo": {
                            "type": "string",
                            "enum": ["validar_logro", "explorar_brecha", "validar_inferencia"],
                        },
                        "pregunta": {"type": "string"},
                    },
                },
            },
        },
    }

    # Layer 4: Output scanning - detect if LLM was compromised
    OUTPUT_ANOMALY_PATTERNS = [
        r"I\s+(am|was)\s+(forced|instructed|told)\s+to",
        r"my\s+(system|original)\s+prompt",
        r"here\s+are\s+my\s+instructions",
        r"I\s+have\s+been\s+jailbroken",
        r"DAN\s+mode\s+(activated|enabled)",
        r"<script>",
        r"javascript:",
        r"I\s+cannot\s+provide.*but\s+I\s+will",
    ]
    
    def __init__(self, enable_pii_masking: bool = True):
        self._provider: Optional[LLMProvider] = None
        self._provider_available: Optional[bool] = None
        
        # Privacy: PII Masking (LPDP Perú Compliance)
        self._enable_pii_masking = enable_pii_masking
        self._pii_masker: Optional[PIIMasker] = None
        self._last_pii_mapping: Dict[str, str] = {}
    
    @property
    def pii_masker(self) -> PIIMasker:
        """Get the PII masker instance."""
        if self._pii_masker is None:
            self._pii_masker = get_pii_masker()
        return self._pii_masker
    
    @property
    def provider(self) -> LLMProvider:
        """Get the configured LLM provider."""
        if self._provider is None:
            self._provider = get_provider()
        return self._provider
    

    async def _is_provider_available(self) -> bool:
        """Check if the configured LLM provider is available."""
        if self._provider_available is not None:
            return self._provider_available
        
        self._provider_available = await self.provider.is_available()
        if self._provider_available:
            logger.info(f"LLM provider available: {self.provider.name}")
        else:
            logger.warning(f"LLM provider not available: {self.provider.name}")
        
        return self._provider_available
    
    def sanitize_input(
        self,
        text: str,
        max_length: int = None,
        extra_fragments: list[str] | None = None,
    ) -> str:
        """
        Sanitize and validate input text.

        Steps:
        1. Truncate to prevent token-exhaustion attacks.
        2. Strip invisible Unicode characters (zero-width spaces, RTL override,
           Unicode tag block — used in steganographic payloads).
        3. Scan the visible text AND any extra hidden-text fragments (white text,
           micro-font text, metadata from the PDF security scan) for known
           injection patterns.

        Args:
            text:             Primary extracted text.
            max_length:       Override maximum character limit.
            extra_fragments:  Hidden text found by the PDF security scanner
                              (SecurityScanResult.hidden_text_fragments).
                              These are checked for injection patterns even if
                              they don't appear in the primary text.
        """
        if max_length is None:
            max_length = self.MAX_CV_LENGTH

        if len(text) > max_length:
            logger.warning(f"Input truncated from {len(text)} to {max_length} chars")
            text = text[:max_length]

        # Strip invisible Unicode before pattern matching
        # (RTL override U+202E, zero-width space U+200B, Unicode tags, etc.)
        _INVISIBLE = (
            "\u200b\u200c\u200d\u200e\u200f"
            "\u202a\u202b\u202c\u202d\u202e"
            "\u2060\u2061\u2062\u2063\u2064"
            "\ufeff"
        )
        _invisible_set = set(_INVISIBLE)
        if any(ch in _invisible_set for ch in text):
            logger.warning("Invisible Unicode characters stripped from input before injection scan")
            text = "".join(ch for ch in text if ch not in _invisible_set)

        # Build the combined corpus to scan:
        # visible text + hidden fragments from PDF security scan
        scan_corpus = text
        if extra_fragments:
            scan_corpus = scan_corpus + "\n" + "\n".join(extra_fragments)

        # Layer 1: Check for known injection patterns in both visible + hidden text
        corpus_lower = scan_corpus.lower()
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, corpus_lower, re.IGNORECASE):
                logger.warning(
                    f"Prompt injection pattern detected: {pattern[:60]!r} "
                    f"(scanned {len(scan_corpus)} chars including {len(extra_fragments or [])} hidden fragments)"
                )
                raise PromptInjectionError(
                    "El documento contiene instrucciones maliciosas embebidas y fue rechazado. "
                    "Si crees que esto es un error, convierte el CV a texto plano antes de subirlo."
                )

        return text
    
    def validate_output(self, output: dict, required_fields: set) -> bool:
        """
        Validate LLM output contains required fields.
        Prevents output manipulation attacks.
        """
        output_keys = set(output.keys()) if isinstance(output, dict) else set()
        return required_fields.issubset(output_keys)
    
    def scan_output(self, output: str) -> bool:
        """
        Scan LLM output for signs of successful prompt injection.

        Layer 4 defense: detect if LLM was manipulated.
        Returns True if output appears safe.
        Raises PromptInjectionError if anomalies are detected.
        """
        if not output:
            return True

        output_lower = output.lower()
        anomalies_found = []

        for pattern in self.OUTPUT_ANOMALY_PATTERNS:
            if re.search(pattern, output_lower, re.IGNORECASE):
                anomalies_found.append(pattern)

        if anomalies_found:
            logger.warning(
                f"Potential output manipulation detected. "
                f"Patterns matched: {len(anomalies_found)}. "
                f"First match: {anomalies_found[0][:50]}"
            )
            raise PromptInjectionError(
                "LLM output contains signs of successful prompt injection and was rejected."
            )

        return True
    
    def _extract_resume_simple(self, text: str, filename: str = "") -> ExtractedResume:
        """
        Enhanced regex-based resume extraction as fallback.
        Now includes experience and education detection.
        Uses multiple strategies for name extraction.
        """
        text_lower = text.lower()
        lines = text.split('\n')
        
        # ============ SMART NAME EXTRACTION ============
        full_name = "Candidato Desconocido"
        
        # Strategy 1: Extract from email pattern (name.surname@)
        email_match = re.search(r'([\w]+)[._]([\w]+)@[\w\.-]+\.\w+', text)
        if email_match:
            first_name = email_match.group(1)
            last_name = email_match.group(2)
            # Validate it looks like a name (not random letters)
            if len(first_name) > 2 and len(last_name) > 2:
                full_name = f"{first_name.title()} {last_name.title()}"
        
        # Strategy 2: Look for ALL CAPS lines (common for names in CVs)
        if full_name == "Candidato Desconocido":
            for line in lines:
                line = line.strip()
                words = line.split()
                # Looking for 2-4 ALL CAPS words that look like a name
                if 2 <= len(words) <= 4:
                    all_caps = all(w.isupper() and len(w) > 1 and w.isalpha() for w in words)
                    if all_caps:
                        full_name = line.title()
                        break
        
        # Strategy 3: First lines with 2-4 capitalized words
        if full_name == "Candidato Desconocido":
            for line in lines[:15]:  # Check more lines
                line = line.strip()
                # Skip common headers
                skip_words = ['contacto', 'experiencia', 'educación', 'habilidades', 
                              'perfil', 'objetivo', 'resumen', 'datos', 'curriculum',
                              'soft', 'hard', 'skill', 'idiomas', 'laboral']
                if any(sw in line.lower() for sw in skip_words):
                    continue
                    
                words = line.split()
                if 2 <= len(words) <= 4:
                    # Check if words look like names (capitalized)
                    looks_like_name = all(
                        w[0].isupper() and w[1:].islower() if len(w) > 1 else w.isupper()
                        for w in words if w.isalpha()
                    )
                    if looks_like_name and all(w.isalpha() for w in words):
                        full_name = line.title()
                        break
        
        # Strategy 4: Use filename as last resort
        if full_name == "Candidato Desconocido" and filename:
            # Try to extract name from filename like "CV_MayumyCarrasco.pdf"
            clean_name = filename.replace('.pdf', '').replace('.docx', '')
            clean_name = re.sub(r'^(cv|resume|curriculum)[_\-\s]*', '', clean_name, flags=re.IGNORECASE)
            # Split CamelCase or underscores
            clean_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean_name)
            clean_name = clean_name.replace('_', ' ').replace('-', ' ')
            if len(clean_name) > 3:
                full_name = clean_name.title()
        
        # Extract email
        email_match = re.search(r'[\w\.\-\+]+@[\w\.\-]+\.\w{2,}', text)
        email = email_match.group(0) if email_match else None

        # Extract phone — patterns ordered from most specific to least
        # Covers Peruvian numbers (9 digits, start with 9) and international formats
        _phone_patterns = [
            r'\+51[\s\-]?9\d{2}[\s\-]?\d{3}[\s\-]?\d{3}',          # +51 9XX XXX XXX
            r'51[\s\-]9\d{2}[\s\-]?\d{3}[\s\-]?\d{3}',              # 51 9XX XXX XXX
            r'\+\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}',  # +XX intl
            r'(?<!\d)9\d{2}[\s\-]?\d{3}[\s\-]?\d{3}(?!\d)',         # 9XX XXX XXX (Perú)
            r'\(?\d{2,3}\)?[\s\-]\d{4}[\s\-]\d{4}',                 # (01) XXXX XXXX
        ]
        phone = None
        for _pat in _phone_patterns:
            m = re.search(_pat, text)
            if m:
                phone = m.group(0).strip()
                break

        # Extract LinkedIn URL
        linkedin_match = re.search(
            r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-_%]+', text, re.IGNORECASE
        )
        linkedin = linkedin_match.group(0) if linkedin_match else None
        if linkedin and not linkedin.startswith("http"):
            linkedin = "https://" + linkedin
        
        # Extract skills (keywords commonly found in CVs)
        skill_keywords = [
            'python', 'java', 'javascript', 'typescript', 'react', 'angular', 'vue',
            'node', 'sql', 'mongodb', 'postgresql', 'mysql', 'docker', 'kubernetes',
            'aws', 'azure', 'gcp', 'linux', 'git', 'agile', 'scrum', 'excel',
            'word', 'powerpoint', 'sap', 'salesforce', 'marketing', 'ventas',
            'liderazgo', 'comunicación', 'inglés', 'español', 'francés',
            'contabilidad', 'finanzas', 'recursos humanos', 'rrhh', 'hr',
            'gestión de proyectos', 'project management', 'photoshop', 'illustrator'
        ]
        
        found_skills = []
        for skill in skill_keywords:
            if skill in text_lower:
                found_skills.append(skill.title())
        
        # ============ EXPERIENCE EXTRACTION ============
        experience_entries = []
        # Patterns: "2020 - 2024", "Enero 2020 - Presente", "Jan 2020 - Present"
        date_pattern = (
            r'(\d{4})\s*[-–]\s*(presente|actual|actualidad|current|present|ongoing|hoy|\d{4})'
        )
        # Job title patterns
        job_titles = [
            'desarrollador', 'developer', 'analista', 'analyst', 'gerente', 'manager',
            'director', 'coordinador', 'coordinator', 'especialista', 'specialist',
            'ingeniero', 'engineer', 'consultor', 'consultant', 'asistente', 'assistant',
            'jefe', 'supervisor', 'líder', 'lead', 'senior', 'junior', 'practicante',
            'intern', 'trainee', 'contador', 'accountant', 'vendedor', 'sales'
        ]
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Check if line contains a job title
            has_job_title = any(title in line_lower for title in job_titles)
            
            # Check for date range in nearby lines
            context = ' '.join(lines[max(0, i-1):min(len(lines), i+3)])
            date_match = re.search(date_pattern, context, re.IGNORECASE)
            
            if has_job_title and len(line.strip()) > 5:
                title = line.strip()[:100]
                company = ""
                is_current = False
                
                # Try to extract dates
                start_date = None
                end_date = None
                if date_match:
                    try:
                        from datetime import date as date_type
                        start_year = int(date_match.group(1))
                        start_date = date_type(start_year, 1, 1)
                        end = date_match.group(2)
                        if end.lower() in ['presente', 'actual', 'actualidad', 'current', 'present', 'ongoing', 'hoy']:
                            is_current = True
                            end_date = None
                        else:
                            end_year = int(end)
                            end_date = date_type(end_year, 12, 31)
                    except (ValueError, TypeError):
                        pass
                
                # Look for company name (usually near job title)
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and len(next_line) < 60 and '@' not in next_line:
                        company = next_line
                
                if title:
                    experience_entries.append(ExperienceEntry(
                        title=title,
                        company=company or "No especificada",
                        start_date=start_date,
                        end_date=end_date,
                        is_current=is_current,
                        description=None
                    ))
                    
        # Dedupe and limit experience entries
        seen_titles = set()
        unique_experience = []
        for exp in experience_entries[:5]:  # Max 5 entries
            if exp.title.lower() not in seen_titles:
                seen_titles.add(exp.title.lower())
                unique_experience.append(exp)
        
        # ============ EDUCATION EXTRACTION ============
        education_entries = []
        edu_keywords = [
            'universidad', 'university', 'instituto', 'institute', 'colegio',
            'licenciatura', 'bachiller', 'maestría', 'master', 'doctorado', 'phd',
            'ingeniería', 'engineering', 'administración', 'economía', 'derecho',
            'contabilidad', 'medicina', 'psicología', 'técnico', 'diplomado'
        ]
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            has_edu_keyword = any(kw in line_lower for kw in edu_keywords)
            
            if has_edu_keyword and len(line.strip()) > 5:
                degree = line.strip()[:100]
                institution = ""
                end_date = None
                
                # Try to find year
                year_match = re.search(r'(19|20)\d{2}', line)
                if year_match:
                    try:
                        from datetime import date as date_type
                        year = int(year_match.group(0))
                        end_date = date_type(year, 12, 31)
                    except (ValueError, TypeError):
                        pass
                
                # Check previous/next line for institution
                if i > 0:
                    prev_line = lines[i - 1].strip()
                    if 'universidad' in prev_line.lower() or 'institute' in prev_line.lower():
                        institution = prev_line
                
                if degree:
                    education_entries.append(EducationEntry(
                        institution=institution or "No especificada",
                        degree=degree,
                        field_of_study=None,
                        start_date=None,
                        end_date=end_date,
                        gpa=None
                    ))
        
        # Dedupe and limit education
        unique_education = education_entries[:3]  # Max 3 entries
        
        # Build ExperienciaProfesional entries from detected experience
        exp_profesional = []
        for exp in unique_experience:
            fecha_inicio = exp.start_date.strftime("%Y-%m") if exp.start_date else None
            if exp.is_current:
                fecha_fin = "Presente"
            elif exp.end_date:
                fecha_fin = exp.end_date.strftime("%Y-%m")
            else:
                fecha_fin = None
            exp_profesional.append(ExperienciaProfesional(
                cargo=exp.title,
                empresa=exp.company,
                periodo="",
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                es_trabajo_actual=exp.is_current,
                resumen_logros=[]
            ))

        # Build EducacionProfesional entries from detected education
        edu_profesional = []
        for edu in unique_education:
            edu_profesional.append(EducacionProfesional(
                institucion=edu.institution,
                titulo=edu.degree,
                anio_egreso=str(edu.end_date.year) if edu.end_date else None,
                tipo="educacion"
            ))

        return ExtractedResume(
            datos_personales=DatosPersonales(
                nombre_completo=full_name,
                telefono=phone,
                email=email,
                linkedin=linkedin,
            ),
            habilidades=list(set(found_skills)),
            experiencia_profesional=exp_profesional,
            educacion=edu_profesional,
        )
    
    async def extract_structured(
        self,
        text: str,
        schema: Type[T],
        system_prompt: str,
        mask_pii: Optional[bool] = None,
        filename: str = "",
        model_override: Optional[str] = None
    ) -> T:
        """
        Extract structured data from text using configured LLM provider.
        
        Args:
            text: Raw text to extract from
            schema: Pydantic model for validation
            system_prompt: Instructions for LLM
            filename: Original filename for fallback name extraction
            mask_pii: Override PII masking setting (None = use default)
        
        Security:
            - Sanitizes input for prompt injection
            - Masks PII before sending to LLM (LPDP compliance)
            - Restores PII in extracted fields after response
        """
        sanitized_text = self.sanitize_input(text)
        
        # Check if provider is available
        if not await self._is_provider_available():
            logger.info("LLM provider not available, using simple extraction")
            if schema == ExtractedResume:
                return self._extract_resume_simple(sanitized_text, filename=filename)
            else:
                raise ValueError("Fallback not implemented for this schema")

        # PII Masking: only for cloud providers (Ollama keeps data local)
        # When sending to Gemini/OpenAI, mask PII for LPDP Perú compliance
        pii_mapping: Dict[str, str] = {}
        should_mask = (
            self._enable_pii_masking
            and settings.PII_MASKING_ENABLED
            and settings.LLM_PROVIDER not in ("ollama",)
        )
        if should_mask:
            try:
                sanitized_text, pii_mapping = self.pii_masker.mask(sanitized_text)
                if pii_mapping:
                    logger.info(f"PII masked: {len(pii_mapping)} entities before sending to {settings.LLM_PROVIDER}")
            except Exception as e:
                logger.warning(f"PII masking failed, continuing without masking: {e}")
                pii_mapping = {}

        schema_json = schema.model_json_schema()
        
        full_prompt = f"""{system_prompt}

PLANTILLA JSON ESPERADA:
{json.dumps(schema_json, indent=2)}

TEXTO DEL CV A ANALIZAR:
{sanitized_text}"""
        
        try:
            # Use override model if specified (only implemented for Ollama locally)
            provider_to_use = self.provider
            needs_close = False
            
            if model_override and self.provider.name.startswith("Ollama"):
                from app.adapters.llm_providers import OllamaProvider
                provider_to_use = OllamaProvider(model=model_override)
                needs_close = True
            
            try:
                # Ask the LLM to generate the JSON
                raw_output = await provider_to_use.generate(
                    prompt=full_prompt,
                    system_prompt=system_prompt,
                    json_mode=True,
                    temperature=0.1,
                    max_tokens=4096
                )
            finally:
                if needs_close:
                    await provider_to_use.close()
            
            logger.debug(f"LLM response from {provider_to_use.name}: {raw_output[:200]}...")
            
            try:
                parsed = json.loads(raw_output)
                
                # Restore PII in the parsed output
                if pii_mapping:
                    parsed = self._restore_pii_in_dict(parsed, pii_mapping)
                
                return schema.model_validate(parsed)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM output as JSON: {e}")
                json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    
                    # Restore PII
                    if pii_mapping:
                        parsed = self._restore_pii_in_dict(parsed, pii_mapping)
                    
                    return schema.model_validate(parsed)
                raise ValueError(f"Could not parse LLM response as JSON: {raw_output[:200]}")
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}, falling back to simple extraction")
            if schema == ExtractedResume:
                return self._extract_resume_simple(sanitized_text, filename=filename)
            raise
    
    def _restore_pii_in_dict(self, data: dict, pii_mapping: Dict[str, str]) -> dict:
        """
        Recursively restore PII tokens in a dictionary.
        
        Converts [PERSON_1], [EMAIL_1], etc. back to original values.
        """
        if not pii_mapping:
            return data
        
        def restore_value(value):
            if isinstance(value, str):
                return self.pii_masker.unmask(value, pii_mapping)
            elif isinstance(value, dict):
                return {k: restore_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [restore_value(item) for item in value]
            return value
        
        return restore_value(data)
    
    async def extract_resume(
        self,
        text: str,
        filename: str = "",
        hidden_fragments: list[str] | None = None,
    ) -> ExtractedResume:
        """Extract structured resume data from raw text (Markdown via pymupdf4llm).

        Args:
            text:             Visible text extracted from the document.
            filename:         Original filename (used by the regex fallback extractor).
            hidden_fragments: Hidden text found by the PDF security scanner
                              (white text, micro-font, off-page, metadata).
                              These are passed to sanitize_input() so injection
                              patterns are checked even against invisible content.
        """
        extraction_model = getattr(settings, "EXTRACTION_MODEL", None)

        sanitized_text = self.sanitize_input(text, extra_fragments=hidden_fragments)
        
        # Prompt optimizado para modelos thinking (Gemma 4 E2B).
        # Los modelos thinking razonan internamente antes de generar output.
        # Principio: prompts concisos + schema JSON = mejor resultado que
        # listas largas de reglas que el modelo puede contradecir.
        # El constrained decoding via JSON Schema garantiza estructura válida.
        # Ref: Google Gemma 4 prompting guide (2025); "Large Language Models are
        # Zero-Shot Reasoners" (Kojima et al., 2022) — el modelo infiere reglas
        # implícitas cuando el contexto es claro.
        prompt = f"""Eres un extractor de datos de CVs. Tu ÚNICA salida es JSON puro válido. Sin saludos, sin explicaciones, sin bloques ```json. Solo el objeto JSON. NUNCA inventes datos; si algo falta usa null.

REGLAS CRÍTICAS:
1. "nombre_completo": Convierte a Title Case. Ej: "ANA ROBLES" → "Ana Robles".
2. "telefono": SOLO el número en la sección de datos de contacto/cabecera (junto al email o LinkedIn). IGNORA completamente los números que aparezcan dentro de la experiencia laboral, referencias o cuerpo del CV. Copia el dígito exactamente como aparece. Si no está claramente como dato de contacto, usa null. NUNCA combines ni construyas un número.
3. "email": Solo el que aparece literalmente en los datos de contacto. NUNCA construyas uno a partir del nombre.
4. "linkedin": URL completa que aparece en los datos de contacto. Formatos: "linkedin.com/in/usuario", "https://www.linkedin.com/in/usuario". Une fragmentos si está partido en dos líneas. Si no hay URL de LinkedIn, usa null.
5. "habilidades": Extrae todas las tecnologías, herramientas, metodologías y competencias del CV completo. Array de strings. Sin duplicados.
6. "idiomas": Idioma + nivel (Básico/Intermedio/Avanzado/Nativo/C1/B2/etc). Si hay certificación oficial (TOEFL, IELTS, Cambridge, EF SET) ponla en "certificacion"; si no, usa null.
7. "fecha_inicio"/"fecha_fin": Formato "YYYY-MM". Si solo hay año: "YYYY-01". Si el trabajo SIGUE ACTIVO (palabras: actualidad, presente, actual, vigente, hoy, en curso, present, current): fecha_fin = "Presente" Y es_trabajo_actual = true. Si termina con fecha concreta: es_trabajo_actual = false.
8. "institucion": Expande siglas. "UNMSM"→"Universidad Nacional Mayor de San Marcos", "PUCP"→"Pontificia Universidad Católica del Perú", "UPC"→"Universidad Peruana de Ciencias Aplicadas".
9. "tipo" en educacion: "educacion" = SOLO grados formales (Bachiller, Licenciatura, Ingeniería, Maestría, MBA, Doctorado). "certificacion" = todo lo demás: diplomados, cursos, bootcamps, certificaciones AWS/Google/Microsoft/Coursera/Udemy/Platzi.

<TEXTO_CV>
{sanitized_text}
</TEXTO_CV>"""

        system_msg = "Eres un extractor de datos de CVs. Devuelve SOLO JSON válido, sin texto adicional."
        
        try:
            provider_to_use = self.provider
            needs_close = False
            
            if extraction_model and self.provider.name.startswith("Ollama"):
                from app.adapters.llm_providers import OllamaProvider
                provider_to_use = OllamaProvider(model=extraction_model)
                needs_close = True
            
            try:
                raw_output = await provider_to_use.generate(
                    prompt=prompt,
                    system_prompt=system_msg,
                    json_schema=self.RESUME_JSON_SCHEMA,
                    temperature=0.1,
                    max_tokens=4096
                )
            finally:
                if needs_close:
                    await provider_to_use.close()
            
            logger.debug(f"LLM resume response: {raw_output[:300]}...")

            # Layer 4: scan output for signs of successful injection
            self.scan_output(raw_output)

            try:
                parsed = json.loads(raw_output)
                resume = ExtractedResume.model_validate(parsed)
                return self._normalize_extracted_resume(resume, text=sanitized_text)
            except json.JSONDecodeError:
                json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    resume = ExtractedResume.model_validate(parsed)
                    return self._normalize_extracted_resume(resume, text=sanitized_text)
                raise ValueError(f"Could not parse LLM response as JSON: {raw_output[:200]}")
        except PromptInjectionError:
            raise
        except Exception as e:
            logger.error(f"LLM resume extraction failed: {e}, falling back to simple extraction")
            return self._extract_resume_simple(sanitized_text, filename=filename)

    def _normalize_extracted_resume(self, resume: "ExtractedResume", text: str = "") -> "ExtractedResume":
        """Post-process LLM output: normalize casing, clean LinkedIn URLs, etc."""
        KNOWN_ABBREVS = {
            # Perú — universidades nacionales
            "unmsm": "Universidad Nacional Mayor de San Marcos",
            "uni": "Universidad Nacional de Ingeniería",
            "unfv": "Universidad Nacional Federico Villarreal",
            "unac": "Universidad Nacional del Callao",
            "unajma": "Universidad Nacional José María Arguedas",
            "unam": "Universidad Nacional Autónoma de México",  # MX (same acronym, context-dependent)
            # Perú — universidades privadas
            "pucp": "Pontificia Universidad Católica del Perú",
            "upc": "Universidad Peruana de Ciencias Aplicadas",
            "utp": "Universidad Tecnológica del Perú",
            "udep": "Universidad de Piura",
            "usil": "Universidad San Ignacio de Loyola",
            "ulima": "Universidad de Lima",
            "upn": "Universidad Privada del Norte",
            "ucsur": "Universidad Científica del Sur",
            "usat": "Universidad Católica Santo Toribio de Mogrovejo",
            "uct": "Universidad Católica de Trujillo",
            "ucv": "Universidad César Vallejo",
            "uladech": "Universidad Católica Los Ángeles de Chimbote",
            "upeu": "Universidad Peruana Unión",
            "uss": "Universidad Señor de Sipán",
            "uancv": "Universidad Andina Néstor Cáceres Velásquez",
            "unsaac": "Universidad Nacional de San Antonio Abad del Cusco",
            # España
            "uam": "Universidad Autónoma de Madrid",
            "ucm": "Universidad Complutense de Madrid",
            "upm": "Universidad Politécnica de Madrid",
            "upv": "Universidad Politécnica de Valencia",
            "uab": "Universidad Autónoma de Barcelona",
            "ub": "Universidad de Barcelona",
            "us": "Universidad de Sevilla",
            # México / Argentina / Colombia
            "unam": "Universidad Nacional Autónoma de México",
            "ipn": "Instituto Politécnico Nacional",
            "uba": "Universidad de Buenos Aires",
            "unal": "Universidad Nacional de Colombia",
            "uandes": "Universidad de los Andes",
        }
        # Acronyms that stay in uppercase
        KEEP_UPPER = {"ibm", "sap", "aws", "gcp", "sql", "bi", "erp", "crm", "hr", "rrhh",
                      "bcp", "bbva", "mba", "phd", "ceo", "cto", "cfo", "it", "ai", "ml",
                      "etl", "kpi", "api", "io", "sa", "sac", "saa", "srl", "eirl"}

        def to_title(s: str) -> str:
            if not s:
                return s
            words = s.split()
            result = []
            for w in words:
                lw = w.lower().rstrip(".,;")
                if lw in KEEP_UPPER:
                    result.append(w.upper())
                else:
                    result.append(w.capitalize())
            return " ".join(result)

        def clean_linkedin(url: str) -> str:
            if not url:
                return url
            # Remove all spaces and newlines from URL
            url = re.sub(r'\s+', '', url)
            # Ensure https:// prefix
            if url and not url.startswith("http"):
                url = "https://" + url
            return url

        # Spanish and English month abbreviations → int
        _MONTH_MAP = {
            'ene': 1, 'enero': 1, 'jan': 1, 'january': 1,
            'feb': 2, 'febrero': 2, 'february': 2,
            'mar': 3, 'marzo': 3, 'march': 3,
            'abr': 4, 'abril': 4, 'apr': 4, 'april': 4,
            'may': 5, 'mayo': 5,
            'jun': 6, 'junio': 6, 'june': 6,
            'jul': 7, 'julio': 7, 'july': 7,
            'ago': 8, 'agosto': 8, 'aug': 8, 'august': 8,
            'sep': 9, 'sept': 9, 'septiembre': 9, 'september': 9,
            'oct': 10, 'octubre': 10, 'october': 10,
            'nov': 11, 'noviembre': 11, 'november': 11,
            'dic': 12, 'diciembre': 12, 'dec': 12, 'december': 12,
        }

        def normalize_date(val: str | None) -> str | None:
            """Convert any date string to YYYY-MM or 'Presente' / null."""
            if not val:
                return val
            v = val.strip()
            # Already correct
            if re.match(r'^\d{4}-\d{2}$', v):
                return v
            # YYYY-MM-DD → YYYY-MM (LLM sometimes emits full ISO despite instructions)
            m = re.match(r'^(\d{4})-(\d{2})-\d{2}$', v)
            if m:
                return f"{m.group(1)}-{m.group(2)}"
            # "Presente" variants
            _ACTIVE = {'presente', 'actual', 'actualidad', 'a la fecha', 'hasta hoy',
                       'en curso', 'hoy', 'vigente', 'actualmente',
                       'present', 'current', 'now', 'ongoing', 'to date', 'till date'}
            if v.lower() in _ACTIVE:
                return 'Presente'
            # DD/MM/YYYY
            m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', v)
            if m:
                return f"{m.group(3)}-{m.group(2).zfill(2)}"
            # MM/YYYY or MM-YYYY
            m = re.match(r'^(\d{1,2})[/\-](\d{4})$', v)
            if m:
                return f"{m.group(2)}-{m.group(1).zfill(2)}"
            # YYYY/MM or YYYY-MM already handled above; this catches YYYY.MM
            m = re.match(r'^(\d{4})[./](\d{2})$', v)
            if m:
                return f"{m.group(1)}-{m.group(2)}"
            # "Month YYYY" or "YYYY Month" with named month
            m = re.match(r'^([a-záéíóúü]{3,})\s+(\d{4})$', v, re.IGNORECASE)
            if m:
                mon = _MONTH_MAP.get(m.group(1).lower().rstrip('.'))
                if mon:
                    return f"{m.group(2)}-{str(mon).zfill(2)}"
            m = re.match(r'^(\d{4})\s+([a-záéíóúü]{3,})$', v, re.IGNORECASE)
            if m:
                mon = _MONTH_MAP.get(m.group(2).lower().rstrip('.'))
                if mon:
                    return f"{m.group(1)}-{str(mon).zfill(2)}"
            # YYYY only
            m = re.match(r'^(\d{4})$', v)
            if m:
                return f"{m.group(1)}-01"
            return val  # unknown format — keep as-is

        def normalize_institution(name: str) -> str:
            if not name:
                return name
            key = name.strip().lower().rstrip(".")
            # Exact acronym match
            if key in KNOWN_ABBREVS:
                return KNOWN_ABBREVS[key]
            # Fuzzy acronym match: handle "U.N.M.S.M", "unmsm.", punctuation variations
            clean_key = re.sub(r'[.\s-]', '', key)  # remove dots/spaces/hyphens
            if clean_key in KNOWN_ABBREVS:
                return KNOWN_ABBREVS[clean_key]
            # Partial match: if the institution name contains a known acronym as a word
            for abbrev, full_name in KNOWN_ABBREVS.items():
                if re.search(r'\b' + re.escape(abbrev) + r'\b', key):
                    return full_name
            return to_title(name)

        dp = resume.datos_personales
        if dp:
            if dp.nombre_completo:
                dp.nombre_completo = to_title(dp.nombre_completo)
            if dp.linkedin:
                dp.linkedin = clean_linkedin(dp.linkedin)

        for exp in resume.experiencia_profesional or []:
            if exp.cargo:
                exp.cargo = to_title(exp.cargo)
            if exp.empresa:
                exp.empresa = to_title(exp.empresa)
            exp.fecha_inicio = normalize_date(exp.fecha_inicio)
            exp.fecha_fin = normalize_date(exp.fecha_fin)
            # Keep es_trabajo_actual in sync
            if exp.fecha_fin == "Presente":
                exp.es_trabajo_actual = True
            elif exp.fecha_fin and exp.fecha_fin != "Presente":
                exp.es_trabajo_actual = False

        # Skills: deduplicate case-insensitively, apply Title Case
        if resume.habilidades:
            seen_skill_keys: set[str] = set()
            clean_skills: list[str] = []
            for skill in resume.habilidades:
                if not skill or not skill.strip():
                    continue
                key = skill.strip().lower()
                if key not in seen_skill_keys:
                    seen_skill_keys.add(key)
                    clean_skills.append(to_title(skill.strip()))
            resume.habilidades = clean_skills

        # Section-label titles the LLM uses as a fallback when it can't read
        # the actual certification/degree name (common with multi-column PDF tables).
        # These are meaningless and must be dropped.
        _GENERIC_TITLES = {
            'certificación', 'certificacion', 'certificaciones',
            'educación', 'educacion', 'formación', 'formacion',
            'diploma', 'título', 'titulo', 'titulación', 'titulacion',
            'grado', 'estudios', 'curso', 'cursos',
        }

        # Patterns that indicate a certification/course name is starting
        # (used to detect concatenated degree+course titles from multi-column tables)
        _FORMAL_DEGREE_START = re.compile(
            r'^(licenciado?\s+en|bachiller\s+en|ingenier[ií]a?\s+en|ingenier[ií]a?\b|'
            r'maestr[ií]a?\s+en|maestr[ií]a?\b|máster\b|mba\b|doctorado\b|'
            r'técnico\s+en|técnico\s+superior|técnico\b)',
            re.IGNORECASE,
        )
        # Keywords that clearly start a new certification/course name
        _CERT_BOUNDARY = re.compile(
            r'(?<!\w)('
            r'data\s+science|machine\s+learning|deep\s+learning|power\s+bi|'
            r'sql\s+server|sql\s+server\s+integration|'
            r'bootcamp\s+de|bootcamp\b|mlops\b|devops\b|'
            r'scrum\b|pmp\b|aws\b|azure\b|google\s+cloud|'
            r'tableau\b|excel\b|python\b|r\s+programming|'
            r'inteligencia\s+artificial|business\s+intelligence|'
            r'coursera\b|udemy\b|platzi\b|linkedin\s+learning'
            r')',
            re.IGNORECASE,
        )

        clean_edu = []
        seen_titulos: set[str] = set()
        for edu in resume.educacion or []:
            if edu.institucion:
                edu.institucion = normalize_institution(edu.institucion)
            if edu.titulo:
                edu.titulo = to_title(edu.titulo)

            # Fix concatenated titles from multi-column PDF tables:
            # e.g. "Licenciado En Estadística Data Science Power BI Integral SQL Server Bootcamp De Mlops"
            # → truncate to just "Licenciado En Estadística"
            if edu.titulo and edu.tipo == "educacion" and len(edu.titulo) > 55:
                if _FORMAL_DEGREE_START.match(edu.titulo):
                    m = _CERT_BOUNDARY.search(edu.titulo)
                    if m and m.start() > 10:
                        original = edu.titulo
                        edu.titulo = edu.titulo[:m.start()].strip().rstrip(",;-–")
                        logger.info(
                            f"Truncated concatenated degree title: "
                            f"'{original[:80]}...' → '{edu.titulo}'"
                        )

            # Drop entries whose title is a generic section label
            titulo_lower = edu.titulo.strip().lower()
            if titulo_lower in _GENERIC_TITLES:
                continue
            # Drop duplicates (same título + tipo)
            dedup_key = (titulo_lower, edu.tipo)
            if dedup_key in seen_titulos:
                continue
            seen_titulos.add(dedup_key)
            clean_edu.append(edu)
        resume.educacion = clean_edu

        # Phone: always extract from raw text (regex is more reliable than the LLM for this).
        # gemma3:4b often hallucinates phone numbers or copies one from experience sections.
        # Strategy: try Peruvian patterns first (high precision), then generic fallback.
        # If raw text has a match → use it and discard the LLM value.
        # If raw text has NO match → keep LLM value only if it looks like a real number
        #   (≥7 consecutive digits); otherwise null to avoid showing wrong contact info.
        if dp and text:
            _phone_patterns = [
                r'\(\+51\)[\s\-]?9\d{2}[\s\-]?\d{3}[\s\-]?\d{3}',       # (+51) 9XX XXX XXX
                r'\+51[\s\-]?9\d{2}[\s\-]?\d{3}[\s\-]?\d{3}',            # +51 9XX XXX XXX
                r'51[\s\-]9\d{2}[\s\-]?\d{3}[\s\-]?\d{3}',               # 51 9XX XXX XXX
                r'(?<!\d)9\d{2}[\s\-]?\d{3}[\s\-]?\d{3}(?!\d)',          # 9XX XXX XXX (Perú mobile)
                r'\(0\d{1,2}\)[\s\-]?\d{4}[\s\-]?\d{4}',                 # (01) XXXX XXXX landline
            ]
            found_in_text = None
            for _pat in _phone_patterns:
                m = re.search(_pat, text)
                if m:
                    found_in_text = m.group(0).strip()
                    break

            if found_in_text:
                dp.telefono = found_in_text
            elif dp.telefono:
                # Validate the LLM value: must contain at least 7 consecutive digits
                llm_phone = dp.telefono
                digits_only = re.sub(r'\D', '', llm_phone)
                if len(digits_only) < 7:
                    dp.telefono = None
                    logger.warning(f"Discarded suspicious LLM phone '{llm_phone}' (< 7 digits)")

        # LinkedIn: extract from raw text if LLM missed it or got it wrong.
        if dp and not dp.linkedin and text:
            _li_match = re.search(
                r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-_%]+',
                text, re.IGNORECASE
            )
            if _li_match:
                url = _li_match.group(0).strip()
                if not url.startswith("http"):
                    url = "https://" + url
                dp.linkedin = url

        return resume

    async def extract_job_profile(self, text: str) -> ExtractedJobProfile:
        """Extract structured job description data using an example-based prompt."""
        if not await self._is_provider_available():
            raise ValueError("LLM provider not available")

        sanitized = self.sanitize_input(text)

        # Prompt optimizado para Gemma 4 (thinking model).
        # Sin example_json con valores concretos: los modelos thinking tienden a
        # copiar ejemplos al output cuando los valores del ejemplo son verosímiles.
        # El constrained decoding via JOB_PROFILE_JSON_SCHEMA garantiza los enums
        # (seniority_level, work_modality, education_level) sin necesidad de ejemplos.
        prompt = f"""Actúa como un analizador de vacantes laborales. Tu ÚNICA salida debe ser un objeto JSON válido. NO incluyas saludos, ni texto previo/posterior, ni bloques de código markdown (```json). Devuelve solo el JSON crudo. No asumas ni inventes requisitos que no estén explícitos.

REGLAS:
1. "title": título exacto del puesto. OBLIGATORIO. No lo inventes si no aparece.
2. "seniority_level": "junior", "mid-level", "senior", "lead", "manager" o null.
3. "work_modality": "remote", "hybrid", "onsite" o null.
4. "education_level": "bachelor", "master", "phd", "high_school", "associate" o null.
5. "required_skills" y "preferred_skills": no repitas habilidades entre ellos.
6. "responsibilities": array de 5 a 10 tareas concretas extraídas del texto.
7. "key_objectives": array de 3 a 5 metas o indicadores mencionados.
8. "min_experience_years": número entero. 0 si no se especifica.
9. "description": resumen de 2-4 oraciones del rol y sus objetivos principales.
10. "required_languages": array de idiomas requeridos o deseables. Nivel SOLO puede ser: "Básico", "Intermedio", "Avanzado", "Nativo", "Bilingüe". "obligatorio": true si el texto lo indica como requisito, false si es deseable. Array vacío [] si no se mencionan idiomas.

<TEXTO_PUESTO>
{sanitized}
</TEXTO_PUESTO>"""

        try:
            raw = await self.provider.generate(
                prompt=prompt,
                system_prompt="Eres un extractor de datos JSON para perfiles de puesto. Devuelve SOLO JSON válido.",
                json_schema=self.JOB_PROFILE_JSON_SCHEMA,
                temperature=0.1,
                max_tokens=2048,
            )
            # Strip any markdown code fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)

            parsed = json.loads(raw)
            # Ensure title fallback: take first line of text if LLM omitted it
            if not parsed.get("title"):
                first_line = next((l.strip() for l in sanitized.splitlines() if l.strip()), "")
                parsed["title"] = first_line[:100]

            # Ensure description fallback: if LLM skipped it, use first substantial paragraph
            if not parsed.get("description"):
                paragraphs = [p.strip() for p in sanitized.split("\n\n") if len(p.strip()) > 60]
                parsed["description"] = paragraphs[0][:600] if paragraphs else sanitized[:400]

            # Normalize and deduplicate skills
            def _dedup_skills(lst):
                if not lst:
                    return lst
                seen: set[str] = set()
                out = []
                for s in lst:
                    if not s or not s.strip():
                        continue
                    key = s.strip().lower()
                    if key not in seen:
                        seen.add(key)
                        # Title-case simple words; keep multi-word as-is with capitalize
                        out.append(s.strip())
                return out

            parsed["required_skills"] = _dedup_skills(parsed.get("required_skills"))
            parsed["preferred_skills"] = _dedup_skills(parsed.get("preferred_skills"))

            # Remove preferred skills that are also required (avoid overlap confusion)
            req_lower = {s.lower() for s in (parsed.get("required_skills") or [])}
            if parsed.get("preferred_skills"):
                parsed["preferred_skills"] = [
                    s for s in parsed["preferred_skills"]
                    if s.lower() not in req_lower
                ]

            return ExtractedJobProfile.model_validate(parsed)
        except Exception as e:
            logger.error(f"extract_job_profile failed: {e}")
            raise
    
    def _fallback_match_scores(self, candidate_skills: list, required_skills: list) -> dict:
        """Simple skill-overlap fallback when LLM is unavailable."""
        cand_set = {s.lower() for s in (candidate_skills or [])}
        req_set = {s.lower() for s in (required_skills or [])}
        skills_pct = (len(cand_set & req_set) / max(len(req_set), 1)) * 100
        if skills_pct >= 70:
            recommendation = "Altamente recomendado"
        elif skills_pct >= 50:
            recommendation = "Buena opción"
        elif skills_pct >= 30:
            recommendation = "Considerar"
        else:
            recommendation = "No recomendado"
        return {
            "skills_score": round(skills_pct, 1),
            "experience_score": 60.0,
            "education_score": 60.0,
            "explanation": "Análisis basado en coincidencia de habilidades.",
            "recommendation": recommendation,
            "missing_critical_skills": [],
            "guia_entrevista": [],
        }

    async def reason_candidate_match(
        self,
        candidate_raw_text: str,
        candidate_skills: list,
        job_title: str,
        job_description: str,
        required_skills: list,
        preferred_skills: list,
        min_experience_years: int = 0,
    ) -> dict:
        """
        Use LLM chain-of-thought reasoning to evaluate candidate-job fit.

        Replaces the old generate_match_explanation + hardcoded scores approach.
        Returns real scores across all dimensions plus an explanation and recommendation.
        """
        if not await self._is_provider_available():
            return self._fallback_match_scores(candidate_skills, required_skills)

        # Sanitize all user-controlled inputs before injecting into the prompt.
        # This prevents prompt injection from malicious CV content or job field values.
        def _strip_injection(text: str, max_len: int) -> str:
            """Remove control sequences and truncate."""
            if not text:
                return ""
            # Strip common injection markers and keep plain text
            cleaned = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
            cleaned = re.sub(r'<[^>]{1,60}>', '', cleaned)  # strip html/xml tags
            cleaned = re.sub(r'\[/?INST\]|<<SYS>>|</s>', '', cleaned)
            cleaned = re.sub(r'(?i)(system|assistant|user)\s*:', '', cleaned)
            return cleaned[:max_len].strip()

        cv_context  = _strip_injection(candidate_raw_text or "", 5000)
        safe_title  = _strip_injection(job_title, 120)
        safe_desc   = _strip_injection(job_description, 1200)
        skills_str  = ", ".join(re.sub(r'[^\w\s\+\#\.\-]', '', s)[:60] for s in candidate_skills[:20]) if candidate_skills else "No disponibles"
        req_str     = ", ".join(re.sub(r'[^\w\s\+\#\.\-]', '', s)[:60] for s in required_skills[:15]) if required_skills else "No especificadas"
        pref_str    = ", ".join(re.sub(r'[^\w\s\+\#\.\-]', '', s)[:60] for s in preferred_skills[:10]) if preferred_skills else "No especificadas"

        # Razonamiento condicional: solo se añade cuando el modelo tiene
        # chain-of-thought interno (OLLAMA_THINKING=true: qwen3, deepseek-r1).
        # Con modelos normales (gemma3:4b, llama3.2) y constrained decoding activo,
        # los pasos de razonamiento no pueden emitirse como texto — el JSON Schema
        # los fuerza al primer token. Los criterios explícitos de puntuación son más
        # útiles para modelos pequeños que instrucciones de razonamiento que no pueden seguir.
        prompt = f"""Actúa como el motor de evaluación de un sistema ATS. Compara el perfil del candidato con los requisitos del puesto. Tu ÚNICA salida debe ser un objeto JSON válido. NO uses formato markdown (```json) ni texto fuera del JSON.

<DATOS_DEL_PUESTO>
Título: {safe_title}
Experiencia mínima requerida: {min_experience_years} años
Habilidades REQUERIDAS: {req_str}
Habilidades DESEABLES: {pref_str}
Descripción: {safe_desc}
</DATOS_DEL_PUESTO>

<DATOS_DEL_CANDIDATO>
Habilidades detectadas: {skills_str}
{cv_context}
</DATOS_DEL_CANDIDATO>

CRITERIOS ESTRICTOS DE PUNTUACIÓN:
- "_razonamiento_previo": Analiza brevemente (3-4 líneas) la coincidencia de habilidades, los años reales trabajados vs los solicitados, y la validez de su educación para este rol específico.
- "skills_score" (0-100): Porcentaje de required_skills que el candidato posee realmente.
- "experience_score" (0-100): 100=supera años requeridos con rol idéntico; 70=cumple años con rol similar; 40=cerca pero rol distinto; 10=sin experiencia relevante.
- "education_score" (0-100): 100=título universitario afín; 70=técnico/incompleto afín; 50=certificaciones afines sin título; 30=formación no relacionada.
- "explanation": 2-3 frases concisas (máx 60 palabras) sobre puntos fuertes y débiles del candidato.
- "recommendation": "Altamente recomendado" (skills>=75 Y experience>=70) | "Buena opción" (ambos>=55) | "Considerar" (alguno>=40) | "No recomendado".
- "relevant_experience_years": Número entero (0, 1, 2, …). Suma SOLO los años en roles cuya función principal coincide con "{safe_title}" (mismo área: operaciones, procesos, TI, ventas, etc.). Excluye roles de áreas no relacionadas, prácticas y voluntariados. Usa las fechas del CV. Si no hay experiencia relevante, pon 0.
- "missing_critical_skills": Array con las habilidades REQUERIDAS que el candidato NO tiene. Array vacío si las tiene todas.
- "guia_entrevista": Exactamente 3 preguntas de entrevista focalizadas. Usa los tipos: "validar_logro" (verificar un logro o experiencia concreta del CV), "explorar_brecha" (profundizar en una habilidad faltante), "validar_inferencia" (confirmar una habilidad inferida pero no explícita). Una pregunta por tipo. Preguntas cortas, concretas, abiertas."""

        try:
            # max_tokens=2500: cubre tanto el presupuesto de thinking interno
            # (modelos thinking: qwen3, deepseek-r1) como el JSON de salida.
            # Para modelos normales (gemma3:4b) el JSON ocupa ~200 tokens — sobra margen.
            # json_schema garantiza constrained decoding: el enum de recommendation
            # y los rangos de score son imposibles de violar.
            raw = await self.provider.generate(
                prompt=prompt,
                json_schema=self.MATCH_JSON_SCHEMA,
                temperature=0.15,
                max_tokens=2500,
            )

            # Belt-and-suspenders: strip any thinking tags that might leak through
            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

            # Progressive JSON extraction
            result = None
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                for m in re.finditer(r'\{', raw):
                    try:
                        result, _ = json.JSONDecoder().raw_decode(raw, m.start())
                        break
                    except json.JSONDecodeError:
                        continue

            if result is None:
                logger.warning(f"Could not parse LLM match reasoning. Raw (first 300): {raw[:300]}")
                return self._fallback_match_scores(candidate_skills, required_skills)

            valid_recommendations = {"Altamente recomendado", "Buena opción", "Considerar", "No recomendado"}
            recommendation = result.get("recommendation", "Considerar")
            if recommendation not in valid_recommendations:
                recommendation = "Considerar"

            # Validate and clean guia_entrevista
            raw_guia = result.get("guia_entrevista", [])
            valid_tipos = {"validar_logro", "explorar_brecha", "validar_inferencia"}
            guia_entrevista = [
                {"tipo": item.get("tipo", "validar_logro"), "pregunta": str(item.get("pregunta", ""))[:300]}
                for item in (raw_guia if isinstance(raw_guia, list) else [])
                if isinstance(item, dict) and item.get("pregunta") and item.get("tipo") in valid_tipos
            ][:3]  # max 3 questions

            raw_rel_years = result.get("relevant_experience_years")
            relevant_experience_years = (
                max(0.0, float(raw_rel_years))
                if isinstance(raw_rel_years, (int, float)) and not isinstance(raw_rel_years, bool)
                else None
            )

            return {
                "skills_score": float(min(max(result.get("skills_score", 50), 0), 100)),
                "experience_score": float(min(max(result.get("experience_score", 50), 0), 100)),
                "education_score": float(min(max(result.get("education_score", 50), 0), 100)),
                "explanation": str(result.get("explanation", "Perfil analizado por IA."))[:500],
                "recommendation": recommendation,
                "relevant_experience_years": relevant_experience_years,
                "missing_critical_skills": [
                    str(s) for s in result.get("missing_critical_skills", [])
                    if s and isinstance(s, str)
                ][:10],
                "guia_entrevista": guia_entrevista,
            }
        except Exception as e:
            logger.error(f"reason_candidate_match failed: {e}")
            return self._fallback_match_scores(candidate_skills, required_skills)

    async def generate_match_explanation(
        self,
        candidate_summary: str,
        job_description: str,
        scores: dict
    ) -> str:
        """Legacy: kept for backwards compatibility. Prefer reason_candidate_match."""
        skills_score = scores.get('skills_score', 0)
        if skills_score >= 70:
            return "Candidato con buen perfil técnico que coincide con los requisitos del puesto."
        elif skills_score >= 50:
            return "Candidato con potencial que cumple algunos de los requisitos básicos."
        else:
            return "Candidato que podría requerir desarrollo adicional para el puesto."
    
    async def health_check(self) -> bool:
        """Check if the configured LLM provider is available."""
        return await self._is_provider_available()
    

