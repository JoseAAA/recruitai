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
import time
import unicodedata
from typing import Optional, Type, TypeVar, Dict, Tuple

from pydantic import BaseModel

from app.core.config import settings
from app.core import validators as _cv
from app.domain.models import (
    ExtractedJobProfile, ExtractedResume, ExperienceEntry, EducationEntry,
    ExperienciaProfesional, EducacionProfesional, DatosPersonales, IdiomaCandidato,
)
from app.adapters.llm_providers import get_provider, LLMProvider, LLMRateLimitError
from app.adapters.pii_masker import get_pii_masker, PIIMasker

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class PromptInjectionError(Exception):
    """Raised when potential prompt injection is detected."""
    pass


# ─── Normalización de niveles de idioma ───────────────────────────────────────
# Mapea variantes (tradicionales en ES/EN + MCER) al canon que usa el sistema.
# Centralizado a nivel de módulo para reutilización (matcher, filtros, reportes)
# y para que sea trivialmente testeable.
_LANG_LEVEL_CANON: dict[str, str] = {
    # Tradicional español/inglés
    "básico": "Básico", "basico": "Básico",
    "elemental": "Básico", "principiante": "Básico",
    "beginner": "Básico", "basic": "Básico",
    "intermedio": "Intermedio", "intermediate": "Intermedio",
    "conversacional": "Intermedio", "conversational": "Intermedio",
    "avanzado": "Avanzado", "advanced": "Avanzado",
    "profesional": "Avanzado", "professional": "Avanzado",
    "fluido": "Avanzado", "fluent": "Avanzado",
    "nativo": "Nativo", "native": "Nativo",
    "bilingüe": "Bilingüe", "bilingue": "Bilingüe", "bilingual": "Bilingüe",
    # MCER
    "a1": "A1", "a2": "A2",
    "b1": "B1", "b2": "B2",
    "c1": "C1", "c2": "C2",
}


def _normalize_lang_level(level: str) -> str:
    """Normaliza un nivel de idioma a la forma canónica.

    Si el nivel no se reconoce (p. ej. ``"100% nativo"`` o un free-text),
    se devuelve trimmed pero sin modificar — preferimos preservar la información
    original a perderla con un mapeo agresivo.
    """
    if not level:
        return level
    return _LANG_LEVEL_CANON.get(level.strip().lower(), level.strip())


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
        "required": [
            "datos_personales",
            "habilidades",
            "idiomas",
            "experiencia_profesional",
            "educacion",
        ],
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
            # Auto-presentación del candidato (párrafo "Perfil profesional" o "About me").
            # Universal en CVs modernos (100% en muestra real). Antes se descartaba.
            "resumen_profesional": {"type": ["string", "null"]},
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
                        # Estatus / progreso. Schema permisivo (string libre) +
                        # normalización en `_normalize_estatus` del domain model.
                        # Crítico en Perú: distingue Bachiller / Titulado / Colegiado /
                        # En curso, requisito frecuente para roles regulados.
                        "estatus": {"type": ["string", "null"]},
                        "fecha_inicio": {"type": ["string", "null"]},
                        "fecha_fin": {"type": ["string", "null"]},
                    },
                },
            },
        },
    }

    JOB_PROFILE_JSON_SCHEMA = {
        "type": "object",
        "required": [
            "title", "description", "required_skills", "preferred_skills", "responsibilities",
        ],
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
            # Lugar de trabajo declarado en el documento (ej. "Lima — San Isidro",
            # "Chinchón", "Trujillo"). Se llena solo si el documento lo menciona
            # explícitamente; null en caso contrario para no inducir alucinación.
            "location": {"type": ["string", "null"]},
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
    
    def _fill_usage(
        self,
        usage_out: Optional[dict],
        provider: "LLMProvider",
        latency_ms: int,
        success: bool = True,
    ) -> None:
        """Vuelca en ``usage_out`` los tokens reales del proveedor + la latencia.

        Patrón seguro ante concurrencia: el llamador (motor) lee
        ``provider.last_usage`` **inmediatamente** después de que ``generate()``
        retorna, sin ningún ``await`` intermedio, por lo que ninguna otra
        corrutina puede sobreescribir el atributo del singleton entre medias.
        ``usage_out`` es siempre propiedad del llamador (uno por llamada), así
        que tampoco se comparte entre tareas concurrentes del matching.

        Si ``usage_out`` es None (el llamador no quiere medir), no hace nada.
        """
        if usage_out is None:
            return
        u = getattr(provider, "last_usage", None) or {}
        usage_out.update(
            {
                "provider": (settings.LLM_PROVIDER or "").lower(),
                "model": getattr(provider, "model", None),
                "input_tokens": u.get("input_tokens"),
                "output_tokens": u.get("output_tokens"),
                "latency_ms": latency_ms,
                "success": success,
            }
        )

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
                
                # Look for company name (usually near job title). El fallback se
                # activa con el LLM caído; mejor dejar la empresa vacía que
                # inventarla con una viñeta de logro o una oración descriptiva.
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if (next_line and len(next_line) < 60 and '@' not in next_line
                            and not re.match(r'^[\-\*•·▪►‣◦]', next_line)
                            and not next_line.endswith('.')):
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
        # Pre-procesado markdown: ver _strip_markdown_noise.
        sanitized_text = self._strip_markdown_noise(sanitized_text)

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
        usage_out: Optional[dict] = None,
    ) -> ExtractedResume:
        """Extract structured resume data from raw text (Markdown via pymupdf4llm).

        Args:
            text:             Visible text extracted from the document.
            filename:         Original filename (used by the regex fallback extractor).
            hidden_fragments: Hidden text found by the PDF security scanner
                              (white text, micro-font, off-page, metadata).
                              These are passed to sanitize_input() so injection
                              patterns are checked even against invisible content.
            usage_out:        Si se provee un dict, el motor vuelca aquí los
                              tokens reales + latencia de la llamada al LLM
                              (para registrar consumo en ``llm_usage``). Ver
                              ``_fill_usage``.
        """
        extraction_model = getattr(settings, "EXTRACTION_MODEL", None)

        sanitized_text = self.sanitize_input(text, extra_fragments=hidden_fragments)
        # Pre-procesado markdown: ver _strip_markdown_noise. Mismo motivo que
        # en extract_job_profile — sin esto, los modelos textuales toman
        # "## **Cargo \\| Empresa (2024)**" como cargo literal en lugar de
        # parsearlo en sus 3 componentes.
        sanitized_text = self._strip_markdown_noise(sanitized_text)

        # Prompt diseñado para modelos pequeños (gemma3:4b, qwen2.5:3b).
        # Vive en backend/app/prompts/extract_cv.md — ver ese archivo y
        # backend/app/prompts/__init__.py para el razonamiento detrás de
        # los principios aplicados (reglas positivas, recency bias, no
        # instrucciones de formato redundantes con el JSON schema).
        # Cambios al texto del prompt se revisan como diff de Markdown.
        from app.prompts import render as _render_prompt

        prompt = _render_prompt("extract_cv", cv_text=sanitized_text)
        system_msg = _render_prompt("extract_cv_system")
        
        try:
            provider_to_use = self.provider
            needs_close = False
            
            if extraction_model and self.provider.name.startswith("Ollama"):
                from app.adapters.llm_providers import OllamaProvider
                provider_to_use = OllamaProvider(model=extraction_model)
                needs_close = True
            
            try:
                # max_tokens proporcional al CV: el JSON de salida nunca supera
                # ~1/3 de los caracteres del CV en tokens. El techo fijo de 8192
                # truncaba menos, pero en proveedores cloud la RESERVA de salida
                # cuenta contra la cuota de tokens/min (Groq free: 12k TPM) —
                # un CV de 1 página reservaba 8192 y agotaba la cuota solo.
                # Piso 2500 (CVs cortos con muchos logros), techo 8192 (CVs 9+ págs).
                _max_out = min(8192, max(2500, len(sanitized_text) // 3))
                _t0 = time.perf_counter()
                raw_output = await provider_to_use.generate(
                    prompt=prompt,
                    system_prompt=system_msg,
                    # json_mode=True para que los proveedores cloud (Groq/OpenAI/
                    # Gemini) activen al menos response_format JSON: ignoran
                    # json_schema y sin esto respondían texto libre, disparando
                    # fallos de parseo y el fallback regex pobre. Ollama da
                    # prioridad a json_schema, así que el modo local no cambia.
                    json_mode=True,
                    json_schema=self.RESUME_JSON_SCHEMA,
                    temperature=0.1,
                    max_tokens=_max_out
                )
                # Capturamos tokens+latencia AQUÍ, antes del finally (que puede
                # cerrar un provider temporal), sin await intermedio → seguro
                # ante concurrencia.
                self._fill_usage(usage_out, provider_to_use, int((time.perf_counter() - _t0) * 1000))
            finally:
                if needs_close:
                    await provider_to_use.close()
            
            logger.debug(f"LLM resume response: {raw_output[:300]}...")

            # Layer 4: scan output for signs of successful injection
            self.scan_output(raw_output)

            # 1) Strip markdown code fences. Some models (gemma4:e2b notably)
            #    wrap JSON in ```json ... ``` even with format=json_schema.
            stripped = raw_output.strip()
            if stripped.startswith("```"):
                stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
                stripped = re.sub(r"\s*```\s*$", "", stripped)

            # Robust 3-tier JSON parsing:
            #   a) strict json.loads — fast path, almost always works
            #   b) regex {...} match + json.loads — handles trailing prose
            #   c) json_repair — handles missing commas, unterminated strings,
            #      stray quotes; common with small models on long, dense CVs.
            parsed = None
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                json_match = re.search(r'\{.*\}', stripped, re.DOTALL)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass
                if parsed is None:
                    try:
                        from json_repair import repair_json
                        repaired = repair_json(stripped)
                        parsed = json.loads(repaired)
                        logger.info("Recovered LLM output via json-repair (model produced malformed JSON)")
                    except Exception:
                        pass
                if parsed is None:
                    raise ValueError(f"Could not parse LLM response as JSON: {raw_output[:200]}")

            # Algunos modelos (Llama 4 Scout, qwen3 thinking, ciertas versiones
            # de Gemini) envuelven el objeto en una lista cuando el schema
            # esperado es dict. Desempaquetamos defensivamente: hace que el
            # código sobreviva a upgrades de modelo sin tocar nada más.
            if isinstance(parsed, list):
                if parsed and isinstance(parsed[0], dict):
                    logger.info(
                        f"LLM wrapped resume JSON in a list "
                        f"({len(parsed)} elements) — unwrapping first element"
                    )
                    parsed = parsed[0]
                else:
                    raise ValueError(
                        "LLM returned a list with non-dict elements; "
                        f"first elem type: {type(parsed[0]).__name__ if parsed else 'empty'}"
                    )

            # 2) Normalize alternate field names some models invent.
            #    gemma4:e2b uses titulo/descripcion instead of cargo/resumen_logros.
            #    Also wraps flat contact fields and converts string idiomas to objects.
            parsed = self._coerce_resume_shape(parsed)

            resume = ExtractedResume.model_validate(parsed)
            return self._normalize_extracted_resume(resume, text=sanitized_text)
        except PromptInjectionError:
            raise
        except LLMRateLimitError:
            # Cuota del proveedor agotada: NO degradar al extractor regex.
            # El regex produce nombres/cargos corruptos que se guardan como
            # buenos; mejor fallar explícito y que el usuario reintente.
            raise
        except Exception as e:
            import traceback
            logger.error(
                f"LLM resume extraction failed [{type(e).__name__}]: {e!r}\n"
                f"{traceback.format_exc()}\nfalling back to simple extraction"
            )
            return self._extract_resume_simple(sanitized_text, filename=filename)

    def _coerce_resume_shape(self, parsed: dict) -> dict:
        """Coerce LLM JSON output to the shape ExtractedResume expects.

        Different LLMs (gemma3:4b vs gemma4:e2b vs gemini) drift in field
        naming and structure. This pre-Pydantic pass normalizes the common
        deviations so a single Pydantic schema works for all of them.

        Handles:
          - Flat contact fields → wrap into datos_personales.
          - experiencia_profesional[]: titulo → cargo, descripcion → resumen_logros,
            periodo → keep, fecha_inicio/fecha_fin filled from periodo if missing.
          - educacion[]: degree → titulo, school → institucion, type → tipo.
          - idiomas[]: convert plain strings to {idioma, nivel:'Intermedio'}.
        """
        if not isinstance(parsed, dict):
            return parsed

        # 1) Flat contact → nested
        if "datos_personales" not in parsed:
            contact_keys = {"nombre_completo", "telefono", "email", "linkedin", "github"}
            flat = {k: parsed.pop(k) for k in list(parsed.keys()) if k in contact_keys}
            if flat:
                parsed["datos_personales"] = flat
                logger.info("Coerced flat contact fields into datos_personales")

        # 2) experiencia_profesional aliases
        exp_list = parsed.get("experiencia_profesional") or []
        if isinstance(exp_list, list):
            for entry in exp_list:
                if not isinstance(entry, dict):
                    continue
                # cargo aliases
                if "cargo" not in entry:
                    for alt in ("titulo", "title", "puesto", "rol", "position"):
                        if alt in entry and entry[alt]:
                            entry["cargo"] = entry.pop(alt)
                            break
                # logros aliases
                if "resumen_logros" not in entry:
                    for alt in ("descripcion", "description", "logros", "achievements", "tareas"):
                        if alt in entry:
                            value = entry.pop(alt)
                            if isinstance(value, str):
                                value = [value] if value.strip() else []
                            elif not isinstance(value, list):
                                value = []
                            entry["resumen_logros"] = value
                            break
                # periodo / start_date / end_date interplay
                if "fecha_inicio" not in entry and "periodo" in entry:
                    # leave periodo as-is; LLM-validated dates can be filled later by post-processor
                    pass

        # 3) educacion aliases
        edu_list = parsed.get("educacion") or []
        if isinstance(edu_list, list):
            for entry in edu_list:
                if not isinstance(entry, dict):
                    continue
                if "titulo" not in entry:
                    for alt in ("degree", "title", "carrera", "programa"):
                        if alt in entry and entry[alt]:
                            entry["titulo"] = entry.pop(alt)
                            break
                if "institucion" not in entry:
                    for alt in ("school", "institution", "universidad", "centro"):
                        if alt in entry and entry[alt]:
                            entry["institucion"] = entry.pop(alt)
                            break
                if "tipo" not in entry:
                    for alt in ("type", "categoria"):
                        if alt in entry and entry[alt]:
                            entry["tipo"] = entry.pop(alt)
                            break

        # 4) idiomas as plain strings → wrap into objects
        idiomas = parsed.get("idiomas") or []
        if isinstance(idiomas, list):
            normalized_idiomas = []
            for item in idiomas:
                if isinstance(item, str):
                    if item.strip():
                        # No inventar el nivel: el prompt PROHÍBE inferir niveles
                        # que el CV no declara. "" se trata como "no especificado"
                        # en la UI y el matcher (no como Intermedio real).
                        normalized_idiomas.append({"idioma": item.strip(), "nivel": ""})
                elif isinstance(item, dict):
                    # ensure required fields exist
                    if "idioma" not in item:
                        for alt in ("language", "name", "lang"):
                            if alt in item:
                                item["idioma"] = item.pop(alt)
                                break
                    if "nivel" not in item:
                        for alt in ("level", "proficiency"):
                            if alt in item:
                                item["nivel"] = item.pop(alt)
                                break
                    if item.get("idioma"):
                        item.setdefault("nivel", "")  # no fabricar un nivel ausente
                        normalized_idiomas.append(item)
            parsed["idiomas"] = normalized_idiomas

        # 5) Make sure required arrays exist
        for key in ("habilidades", "idiomas", "experiencia_profesional", "educacion"):
            if key not in parsed or parsed[key] is None:
                parsed[key] = []

        return parsed

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

        def strip_markdown(s: str) -> str:
            """Remove markdown formatting characters that the LLM sometimes
            copies verbatim into extracted fields when the source markdown
            uses ## headers and ** bold (e.g. "## **Cargo | 2020-2024**").
            Conservative: only strips wrapping syntax, never alphanumeric content.
            """
            if not s:
                return s
            s = s.strip()
            # Drop leading hashes (## ###) used as markdown headers
            s = re.sub(r'^#+\s*', '', s)
            # Strip bold/italic wrappers (** __  *  _) keeping the inner text
            for _ in range(3):  # handle nested **__text__**
                s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
                s = re.sub(r'__(.+?)__', r'\1', s)
                s = re.sub(r'~~(.+?)~~', r'\1', s)
            # Remove leftover stray formatting characters at the edges
            s = re.sub(r'^[\*_~`#\s]+', '', s)
            s = re.sub(r'[\*_~`\s]+$', '', s)
            # Backtick code wrappers
            s = s.replace('`', '')
            return s.strip()

        def is_bullet_logro(s: str) -> bool:
            """Detect strings that are achievement bullets, not job titles.
            Generic heuristic — does not depend on language or specific words.
            """
            if not s:
                return False
            stripped = s.strip()
            # Bullet markers at start
            if re.match(r'^[\-\*•·▪▫►‣◦]\s', stripped):
                return True
            # Long sentence-like text: los cargos son títulos cortos; los logros,
            # descripciones. Pero existen cargos largos legítimos en español
            # ("Coordinador de Seguridad y Salud en el Trabajo y Gestión Ambiental
            # Corporativa..."), así que la longitud sola NO basta: solo lo tratamos
            # como logro si además se lee como oración (termina en punto) o es
            # extremadamente largo.
            if ' ' in stripped and (
                (len(stripped) > 90 and stripped.endswith('.')) or len(stripped) > 160
            ):
                return True
            return False

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

        def dedupe_repeated_phrase(s: str) -> str:
            # Collapse "Miranda Naser Miranda Naser" → "Miranda Naser".
            # Designed CVs often render the candidate name twice (script logo +
            # body text) and small models concatenate both occurrences.
            if not s:
                return s
            tokens = s.split()
            n = len(tokens)
            for half in range(n // 2, 0, -1):
                if n % half == 0 and all(
                    tokens[i] == tokens[i % half] for i in range(n)
                ):
                    return " ".join(tokens[:half])
            return s

        def clean_linkedin(url: str) -> str | None:
            # Returns None for any URL that lacks a real username after /in/.
            # Without a username, LinkedIn redirects clicks to the *viewer's* own
            # profile, which makes it look like the candidate's data was leaked
            # from another CV. Rejecting at extraction time avoids that confusion.
            if not url:
                return None
            url = re.sub(r'\s+', '', url)
            if not url.startswith("http"):
                url = "https://" + url
            m = re.search(r'linkedin\.com/in/([\w\-_%]+)', url, re.IGNORECASE)
            if not m or not m.group(1):
                return None
            return url

        def normalize_date(val: str | None, is_end: bool = False) -> str | None:
            """Convert any date string to YYYY-MM or 'Presente' / null.

            Strategy: try cheap regexes first for the common YYYY-MM and
            YYYY-MM-DD shapes, then fall back to ``dateparser`` which handles
            200+ language variants ("Set 2016", "Setiembre 2020", "Janeiro 2018",
            typos). When only a year is present, starts default to January and
            ends default to December so a "2015 - 2017" range covers a full
            ~3 years instead of being clipped to ~2.
            """
            if not val:
                return val
            v = val.strip()
            # Already YYYY-MM (the format we want to land on)
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
            # YYYY only — pad to Jan for starts, Dec for ends.
            m = re.match(r'^(\d{4})$', v)
            if m:
                return f"{m.group(1)}-{'12' if is_end else '01'}"

            # dateparser fallback — handles "Set 2016", "Setiembre 2020",
            # "Janeiro 2018", "marzo de 2020", typos, mixed punctuation and
            # dozens of other variants we'd otherwise enumerate by hand.
            # "Agos" (4-letter agosto abbreviation) is the one known blind spot.
            try:
                import dateparser
                v_norm = re.sub(r'\bAgos\b', 'Agosto', v, flags=re.IGNORECASE)
                parsed = dateparser.parse(
                    v_norm,
                    languages=['es', 'pt', 'en'],
                    settings={'PREFER_DAY_OF_MONTH': 'last' if is_end else 'first'},
                )
                if parsed:
                    # Si el input NO traía un año de 4 dígitos, dateparser lo
                    # rellena con el año ACTUAL — generando fechas futuras falsas
                    # (ej. "Setiembre" → 2026-09). No inventamos el año: dejamos
                    # el valor original sin tocar en vez de afirmar una fecha mala.
                    if not re.search(r'\d{4}', v):
                        return val
                    return f"{parsed.year}-{str(parsed.month).zfill(2)}"
            except Exception:
                pass

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
            # Partial match: si el nombre contiene una sigla conocida como
            # palabra. Restringido a siglas de >= 4 letras: las cortas ('us',
            # 'ub', 'uni') colisionan con palabras o con centros distintos
            # (un "Centro de Idiomas UNI" NO es la Universidad Nacional de
            # Ingeniería). Las siglas exactas ya se resuelven arriba.
            for abbrev, full_name in KNOWN_ABBREVS.items():
                if len(abbrev) >= 4 and re.search(r'\b' + re.escape(abbrev) + r'\b', key):
                    return full_name
            return to_title(name)

        dp = resume.datos_personales
        if dp:
            if dp.nombre_completo:
                # normalize_person_name respeta las partículas hispanas
                # ("de la Cruz", "del Carmen", "de los Ríos"); to_title las
                # rompía a "De La Cruz". Aplicamos tras limpiar markdown/duplicados.
                _cleaned_name = dedupe_repeated_phrase(strip_markdown(dp.nombre_completo))
                dp.nombre_completo = _cv.normalize_person_name(_cleaned_name) or _cleaned_name
            if dp.linkedin:
                dp.linkedin = clean_linkedin(dp.linkedin)

        # Filter and clean experiencia_profesional:
        # - strip markdown formatting from cargo and empresa
        # - drop entries whose cargo is actually an achievement bullet (logro)
        clean_exp = []
        for exp in resume.experiencia_profesional or []:
            if exp.cargo:
                exp.cargo = strip_markdown(exp.cargo)
            if exp.empresa:
                exp.empresa = strip_markdown(exp.empresa)

            # Skip entries that are actually logros, not real jobs
            if exp.cargo and is_bullet_logro(exp.cargo):
                logger.info(f"Dropped bullet-logro mistakenly extracted as cargo: {exp.cargo[:60]!r}")
                continue

            if exp.cargo:
                exp.cargo = to_title(exp.cargo)
            if exp.empresa:
                exp.empresa = to_title(exp.empresa)
            exp.fecha_inicio = normalize_date(exp.fecha_inicio)
            exp.fecha_fin = normalize_date(exp.fecha_fin, is_end=True)
            # Keep es_trabajo_actual in sync
            if exp.fecha_fin == "Presente":
                exp.es_trabajo_actual = True
            elif exp.fecha_fin and exp.fecha_fin != "Presente":
                exp.es_trabajo_actual = False
            clean_exp.append(exp)

        # Dedup: solo colapsamos cuando empresa + fecha_inicio + CARGO coinciden.
        # Incluir el cargo en la clave es clave: dos cargos DISTINTOS en la misma
        # empresa con la misma fecha de inicio son un ascenso/rol legítimo
        # ("Analista" → "Jefe de Proyectos" en el BCP), NO un duplicado. Antes la
        # clave era solo (empresa, fecha_inicio) y borraba el ascenso.
        deduped: list = []
        seen_keys: set[tuple] = set()  # (empresa_lc, fecha_inicio, cargo_lc)
        for exp in clean_exp:
            empresa_key = (exp.empresa or '').strip().lower()
            start_key = exp.fecha_inicio or ''
            cargo_key = re.sub(r'\s+', ' ', (exp.cargo or '').strip().lower())
            if not empresa_key:
                deduped.append(exp)
                continue
            key = (empresa_key, start_key, cargo_key)
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(exp)
            else:
                logger.info(
                    f"Dedup experiencia: descartado duplicado exacto "
                    f"{exp.cargo!r} en {exp.empresa!r} ({start_key})"
                )
        resume.experiencia_profesional = deduped

        # ── Hallucination guard ───────────────────────────────────────────────
        # Small models (gemma3:4b) sometimes invent fields when a CV's markdown
        # structure is irregular. The failure modes we see in practice:
        #   1. cargo == empresa (model couldn't tell title from company,
        #      copied the same string into both fields).
        #   2. cargo or empresa is text the model hallucinated — does not
        #      appear anywhere in the original document.
        # We trust the raw_text as ground truth: any value that isn't a
        # case-insensitive substring of it is dropped. The recruiter can fill
        # the missing field via the manual edit UI, which is far less risky
        # than letting a phantom company sit in the matching pipeline.
        if text:
            # Normalizamos el texto fuente UNA vez con la MISMA forma que los
            # valores a comparar: NFC (los PDFs de Mac/InDesign emiten acentos
            # descompuestos — 'ñ' = 'n'+◌̃ — que diferían byte a byte del valor
            # ya normalizado a NFC por Pydantic) y colapso de espacios (pymupdf
            # parte cargos/empresas en varios renglones). Sin ambos lados
            # normalizados igual, el guardia borraba experiencia legítima con
            # tildes/ñ o cuyo cargo/empresa venía partido en líneas del PDF.
            text_lc = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text).lower())

            def _in_text(value: str | None) -> bool:
                if not value:
                    return True  # None passes through; only positive values are checked
                # Mismo normalizado que el haystack: NFC + espacios colapsados.
                v = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', value).strip().lower())
                return bool(v) and v in text_lc

            validated: list = []
            for exp in resume.experiencia_profesional or []:
                cargo = (exp.cargo or '').strip()
                empresa = (exp.empresa or '').strip()

                # 1) cargo == empresa → the model duplicated. Keep one, blank
                #    the other so the recruiter notices and fills it in.
                if cargo and empresa and cargo.lower() == empresa.lower():
                    logger.warning(
                        f"Halu-guard: cargo == empresa ({cargo!r}) — clearing empresa"
                    )
                    exp.empresa = None
                    empresa = ''

                # 2) substring presence in raw_text. We only drop values that
                #    are clearly absent — a partial overlap (e.g. "Bdo Perú"
                #    vs "BDO Perú S.A.C.") still counts as present.
                if cargo and not _in_text(cargo):
                    logger.warning(
                        f"Halu-guard: cargo {cargo!r} not found in raw_text — clearing"
                    )
                    exp.cargo = None
                    cargo = ''
                if empresa and not _in_text(empresa):
                    logger.warning(
                        f"Halu-guard: empresa {empresa!r} not found in raw_text — clearing"
                    )
                    exp.empresa = None
                    empresa = ''

                # 3) cargo and empresa should sit close together in the raw
                #    text. When the minimum distance between any occurrence of
                #    one and any occurrence of the other is large, the model
                #    almost certainly fused a title from one block with a
                #    company from another (a known gemma3:4b failure on CVs
                #    with non-uniform markdown). Empirical measurement on real
                #    CVs: legitimate same-block pairs sit within 100-400 chars
                #    of each other; observed cross-block merges show up at
                #    1000+ chars. 800 keeps a comfortable margin on both sides.
                if cargo and empresa:
                    cargo_lc_norm = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', cargo).lower())
                    empresa_lc_norm = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', empresa).lower())
                    c_positions = [
                        m.start() for m in re.finditer(re.escape(cargo_lc_norm), text_lc)
                    ]
                    e_positions = [
                        m.start() for m in re.finditer(re.escape(empresa_lc_norm), text_lc)
                    ]
                    if c_positions and e_positions:
                        min_dist = min(
                            abs(cp - ep) for cp in c_positions for ep in e_positions
                        )
                        if min_dist > 800:
                            # Distancia grande NO siempre es fusión: en el
                            # formato de ascensos (empresa UNA vez como título
                            # + varios cargos debajo, clásico en CVs peruanos)
                            # los cargos antiguos quedan a 1000-2500 chars de
                            # la empresa. Borrar aquí eliminaba la historia de
                            # promociones (CV real: 4 cargos en Danper → 1).
                            # Es fusión cross-block solo si OTRA empresa de la
                            # extracción está claramente más cerca del cargo.
                            other_empresas = {
                                re.sub(r'\s+', ' ', unicodedata.normalize(
                                    'NFC', (o.empresa or '')).strip().lower())
                                for o in (resume.experiencia_profesional or [])
                                if o is not exp and o.empresa
                            }
                            other_empresas.discard(empresa_lc_norm)
                            other_empresas.discard('')
                            closer_other = False
                            for oe in other_empresas:
                                o_positions = [
                                    m.start() for m in re.finditer(re.escape(oe), text_lc)
                                ]
                                if not o_positions:
                                    continue
                                o_dist = min(
                                    abs(cp - op)
                                    for cp in c_positions for op in o_positions
                                )
                                if o_dist < 400 and o_dist < min_dist:
                                    closer_other = True
                                    break
                            if closer_other:
                                logger.warning(
                                    f"Halu-guard: cargo {cargo!r} and empresa "
                                    f"{empresa!r} are {min_dist} chars apart and "
                                    "another empresa sits closer — cross-block "
                                    "merge, dropping entry"
                                )
                                continue
                            logger.info(
                                f"Halu-guard: cargo {cargo!r} lejos de empresa "
                                f"{empresa!r} ({min_dist} chars) pero sin otra "
                                "empresa más cercana — layout de ascensos, se conserva"
                            )

                # 4) entry with neither cargo nor empresa is unusable noise.
                if not cargo and not empresa:
                    logger.warning(
                        f"Halu-guard: dropping experience entry with no usable fields "
                        f"(was cargo={exp.cargo!r}, empresa={exp.empresa!r})"
                    )
                    continue

                validated.append(exp)
            resume.experiencia_profesional = validated

        # Completeness check: rough heuristic to flag CVs where the LLM
        # likely missed jobs. Counts how many independent date ranges the
        # raw text contains inside the experience section. If the LLM
        # produced significantly fewer entries than that, log a warning so
        # the recruiter knows to verify (and can use the manual edit UI
        # to add what's missing). Pure logging — never silently mutates.
        if text:
            # Restrict scan to the experience block when a header is detected,
            # so academic dates from FORMACION don't inflate the count.
            scan_window = text
            for marker in (
                "EXPERIENCIA LABORAL", "EXPERIENCIA PROFESIONAL",
                "EXPERIENCE", "EMPLOYMENT HISTORY", "WORK EXPERIENCE",
            ):
                if marker in text.upper():
                    start = text.upper().index(marker)
                    end_marker = None
                    for stop in ("FORMACIÓN", "FORMACION", "EDUCACIÓN", "EDUCACION",
                                 "EDUCATION", "ACADEMIC", "ESTUDIOS",
                                 "REFERENCIAS", "REFERENCES"):
                        if stop in text.upper()[start + len(marker):]:
                            stop_idx = text.upper().index(stop, start + len(marker))
                            if end_marker is None or stop_idx < end_marker:
                                end_marker = stop_idx
                    scan_window = text[start:end_marker] if end_marker else text[start:]
                    break

            # A rough job-block count: distinct year-pair date ranges
            # ("2020-2024", "Ene 2020 – Dic 2024", "08/2017 – 02/2018").
            # Each typically corresponds to one job block.
            date_range_re = re.compile(
                r'(?:\d{1,2}/\d{4}|\d{4}|\b(?:ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic|'
                r'jan|apr|aug|dec)[a-zñ]*\s+\d{4})'
                r'\s*[-–—a]\s*'
                r'(?:\d{1,2}/\d{4}|\d{4}|\b(?:ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic|'
                r'jan|apr|aug|dec)[a-zñ]*\s+\d{4}|actualidad|presente|actual|hoy|present|current)',
                re.IGNORECASE,
            )
            detected_ranges = len(date_range_re.findall(scan_window))
            extracted_count = len(resume.experiencia_profesional or [])
            # Only fire on meaningful gaps (≥ 3 missing). The heuristic over-
            # counts by ~1-2 because logros sometimes contain year ranges, so
            # we leave a tolerance margin to avoid false positives on shorter CVs.
            if detected_ranges >= 5 and extracted_count <= detected_ranges - 3:
                logger.warning(
                    f"Posible extracción incompleta: {detected_ranges} rangos de fecha "
                    f"detectados en la sección de experiencia, pero solo se extrajeron "
                    f"{extracted_count} experiencias. El recruiter podría revisar y "
                    f"agregar las faltantes desde el panel del candidato."
                )

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
                edu.institucion = normalize_institution(strip_markdown(edu.institucion))
            if edu.titulo:
                edu.titulo = to_title(strip_markdown(edu.titulo))

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
            # Drop duplicates: mismo título + tipo + INSTITUCIÓN. Antes la clave
            # ignoraba la institución, así que el mismo diplomado en dos centros
            # (PUCP y ESAN), o dos institutos distintos con título vacío (tabla
            # multi-columna), colapsaban y se perdía una credencial real.
            instit_lower = (edu.institucion or '').strip().lower()
            dedup_key = (titulo_lower, edu.tipo, instit_lower)
            # Un título vacío NO es evidencia de duplicado: nunca descartes por él.
            if titulo_lower and dedup_key in seen_titulos:
                continue
            seen_titulos.add(dedup_key)
            clean_edu.append(edu)
        resume.educacion = clean_edu

        # Phone: always extract from raw text (regex is more reliable than the LLM for this).
        # gemma3:4b often hallucinates phone numbers or copies one from experience sections.
        # Strategy: try patterns ordered by specificity, fall back to a permissive
        # international pattern that accepts country code in parens, dashes, dots
        # or spaces — covers the layouts that small models miss.
        # If raw text has a match → use it and discard the LLM value.
        # If raw text has NO match → keep LLM value only if it looks like a real number
        #   (≥7 consecutive digits); otherwise null to avoid showing wrong contact info.
        if dp and text:
            _phone_patterns = [
                r'\(\+?\d{1,3}\)[\s\-\.]{0,3}\d{2,4}[\s\-\.]{0,3}\d{3,4}[\s\-\.]{0,3}\d{3,4}',  # (+CC) XXX XXX XXX
                r'\+\d{1,3}[\s\-\.]{0,3}\d{2,4}[\s\-\.]{0,3}\d{3,4}[\s\-\.]{0,3}\d{3,4}',       # +CC XXX XXX XXX
                r'(?<!\d)9\d{2}[\s\-\.]{0,3}\d{3}[\s\-\.]{0,3}\d{3}(?!\d)',                       # 9XX XXX XXX (Perú móvil)
                r'\(0\d{1,2}\)[\s\-\.]{0,3}\d{4}[\s\-\.]{0,3}\d{4}',                              # (01) XXXX XXXX (fijo PE)
                r'(?<!\d)\d{2,4}[\s\-\.]\d{3,4}[\s\-\.]\d{3,4}(?!\d)',                            # genérico XX-XXX-XXXX
            ]
            # Buscar el teléfono en la REGIÓN DE CABECERA (hasta la primera
            # sección), no en todo el documento: así no tomamos el número de una
            # referencia o de un empleador listado más abajo como si fuera el del
            # candidato.
            _header_end = 700
            _up = text.upper()
            for _stop in ("EXPERIENCIA", "FORMACIÓN", "FORMACION", "EDUCACIÓN",
                          "EDUCACION", "EDUCATION", "EXPERIENCE", "REFERENCIAS",
                          "REFERENCES"):
                _idx = _up.find(_stop)
                if 0 <= _idx < _header_end:
                    _header_end = _idx
            header = text[:_header_end]
            found_in_text = None
            for _pat in _phone_patterns:
                m = re.search(_pat, header)
                if m:
                    found_in_text = m.group(0).strip()
                    break

            if found_in_text:
                # Normalizar a E.164 antes de guardar: la asignación directa NO
                # re-dispara el validador Pydantic, así que sin esto quedaban
                # formatos mezclados entre candidatos.
                dp.telefono = _cv.normalize_phone(found_in_text) or found_in_text
            elif dp.telefono:
                # Validate the LLM value: must contain at least 7 consecutive digits
                llm_phone = dp.telefono
                digits_only = re.sub(r'\D', '', llm_phone)
                if len(digits_only) < 7:
                    dp.telefono = None
                    logger.warning(f"Discarded suspicious LLM phone '{llm_phone}' (< 7 digits)")
                else:
                    dp.telefono = _cv.normalize_phone(llm_phone) or llm_phone

        # LinkedIn: extract from raw text if LLM missed it or got it wrong.
        if dp and not dp.linkedin and text:
            _li_match = re.search(
                r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-_%]+',
                text, re.IGNORECASE
            )
            if _li_match:
                url = _li_match.group(0).strip()
                # Pasar por el normalizador canónico (igual que el validador).
                dp.linkedin = _cv.normalize_linkedin(url) or (
                    url if url.startswith("http") else "https://" + url
                )

        # Email: si el LLM no lo extrajo, recuperarlo del texto crudo.
        # El LLM pequeño a veces lo omite cuando está en una columna lateral o
        # separado del nombre por un salto de línea inusual.
        if dp and not dp.email and text:
            _email_match = re.search(
                r'[\w\.\-\+]+@[\w\.\-]+\.\w{2,}', text
            )
            if _email_match:
                _raw_email = _email_match.group(0).strip()
                # Normalizar (lowercase de dominio, IDN) como hace el validador.
                dp.email = _cv.normalize_email(_raw_email, check_deliverability=False) or _raw_email

        # Idiomas: normalizar variantes ("Conversacional", "Profesional", "Fluent", etc.)
        # al canon que usa el frontend y el matcher. Esto es crítico para:
        #   - Coherencia en filtros del frontend (que comparan strings exactos).
        #   - Calidad del embedding del campo "summary" donde se serializan idiomas.
        #   - Calidad del matching de idiomas en `reason_candidate_match`.
        # Se mantiene `_LANG_LEVEL_CANON` como mapping global (tradicional + MCER).
        if resume.idiomas:
            for idioma in resume.idiomas:
                if idioma.nivel:
                    idioma.nivel = _normalize_lang_level(idioma.nivel)

        return resume

    @staticmethod
    def _strip_markdown_noise(text: str) -> str:
        """Elimina ruido markdown (`**bold**`, `## header`) que confunde al LLM.

        PyMuPDF4LLM y MarkItDown emiten markdown estructural. Los humanos lo
        leen como "esto es un header" o "esto es bold", pero un LLM textual
        ve los caracteres `*` y `#` como parte del contenido y los puede
        copiar literal (vimos el bug donde "**PERFIL DE PUESTO**" terminó
        como título de vacante).

        Esta función NO destruye estructura: conserva saltos de línea, bullets
        `-`, listas numeradas, párrafos. Solo elimina los caracteres de énfasis
        y los `#` de headers, dejando el TEXTO de cada header en su línea con
        un salto de línea antes y después que preserva la jerarquía visual.

        Aplicación: en ``extract_resume`` y ``extract_job_profile`` ANTES de
        inyectar el texto en el prompt. Es agnóstico al tipo de documento
        (CV, perfil de puesto, cualquier otro) y al formato origen (PDF o DOCX).
        """
        if not text:
            return text
        # Remove ATX headers (## Title -> Title), preserving the text.
        text = re.sub(r'^\s{0,3}#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Remove bold/italic markers but keep the inner text.
        # Order matters: triple first (***), then double (**), then single (*).
        text = re.sub(r'\*{3}(.+?)\*{3}', r'\1', text)
        text = re.sub(r'\*{2}(.+?)\*{2}', r'\1', text)
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
        # Underscore-based emphasis: PyMuPDF4LLM emite tanto __bold__ como
        # _italic_ (un solo underscore). Cubrir ambos. El single-underscore
        # se hace con lookarounds para no destruir snake_case en código /
        # nombres de variables.
        text = re.sub(r'_{2,3}([^_\n]+?)_{2,3}', r'\1', text)
        text = re.sub(r'(?<![A-Za-z0-9_])_([^_\n]{1,200}?)_(?![A-Za-z0-9_])', r'\1', text)
        # Mixed combos PyMuPDF emite ocasionalmente: _**texto**_ , **_texto_**
        # ya quedaron cubiertos por las pasadas anteriores en orden.
        # Remove leftover empty lines that this cleanup may have produced.
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    async def extract_job_profile(
        self, text: str, usage_out: Optional[dict] = None
    ) -> ExtractedJobProfile:
        """Extract structured job description data using an example-based prompt."""
        if not await self._is_provider_available():
            raise ValueError("LLM provider not available")

        sanitized = self.sanitize_input(text)
        # Pre-procesado: eliminar ruido markdown que el LLM puede tomar literal.
        sanitized = self._strip_markdown_noise(sanitized)

        # Prompt y system message viven en backend/app/prompts/extract_job.md
        # y extract_job_system.md. Diseño: arrays SIN tamaños mínimos para
        # no inducir alucinación (el modelo inventa relleno si pides "5 a 10
        # tareas" y el documento solo trae 2).
        from app.prompts import render as _render_prompt

        prompt = _render_prompt("extract_job", job_text=sanitized)
        system_msg = _render_prompt("extract_job_system")

        try:
            _t0 = time.perf_counter()
            raw = await self.provider.generate(
                prompt=prompt,
                system_prompt=system_msg,
                json_mode=True,  # cloud: activa response_format JSON (ver extract_resume)
                json_schema=self.JOB_PROFILE_JSON_SCHEMA,
                temperature=0.1,
                max_tokens=2048,
            )
            self._fill_usage(usage_out, self.provider, int((time.perf_counter() - _t0) * 1000))
            # Strip any markdown code fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```\s*$", "", raw)

            # Robust 3-tier parsing — same as extract_resume. Small models
            # (gemma4:e2b) sometimes return empty content, leading prose,
            # or JSON with a missing comma. We try strict first, then a
            # {...} regex extraction, then json_repair as a last resort.
            parsed = None
            if raw:
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
                    if json_match:
                        try:
                            parsed = json.loads(json_match.group())
                        except json.JSONDecodeError:
                            pass
                    if parsed is None:
                        try:
                            from json_repair import repair_json
                            parsed = json.loads(repair_json(raw))
                            logger.info("Recovered job-profile output via json-repair")
                        except Exception:
                            pass

            # Algunos modelos (Llama 4 Scout, qwen3 en thinking mode, ciertas
            # versiones de Gemini) envuelven el objeto en una lista —
            # devuelven ``[{...}]`` cuando el schema pedido es un objeto.
            # Hacemos el código defensivo desempaquetando si llegó así. Esto
            # evita que un upgrade de modelo rompa la extracción.
            if isinstance(parsed, list):
                if parsed and isinstance(parsed[0], dict):
                    logger.info(
                        f"LLM wrapped job-profile JSON in a list "
                        f"({len(parsed)} elements) — unwrapping first element"
                    )
                    parsed = parsed[0]
                else:
                    logger.warning(
                        "LLM returned a list but elements are not dicts — falling back"
                    )
                    parsed = None

            # Helper compartido: encuentra la primera línea "real" del documento
            # saltando encabezados de plantilla y residuos markdown.
            def _first_real_title(text: str) -> str:
                template_headers = {
                    "perfil de puesto", "perfil del puesto", "perfil",
                    "descripcion del puesto", "descripcion del cargo",
                    "job description", "job profile", "position description",
                    "job", "puesto", "cargo", "vacante",
                }
                for raw_line in text.splitlines():
                    candidate = raw_line.strip()
                    if not candidate:
                        continue
                    # Limpia residuos de markdown que strip_markdown_noise no
                    # haya cubierto (separadores, signos al inicio/fin).
                    candidate = re.sub(r'^[\*#\-_=\s]+', '', candidate).strip()
                    candidate = re.sub(r'[\*#_=]+$', '', candidate).strip()
                    if not candidate:
                        continue
                    normalized = re.sub(r'[^a-zA-Záéíóúñü\s]', '', candidate).strip().lower()
                    if normalized in template_headers:
                        continue
                    return candidate
                return ""

            if parsed is None:
                # Final safety net: build a minimal stub from the first
                # paragraph so the recruiter at least sees the document
                # accepted and can complete the form manually.
                logger.warning("LLM returned unparseable response — falling back to minimal stub")
                first_line = _first_real_title(sanitized)
                paragraphs = [p.strip() for p in sanitized.split("\n\n") if len(p.strip()) > 60]
                parsed = {
                    "title": first_line[:100] or "Puesto sin título",
                    "description": paragraphs[0][:600] if paragraphs else sanitized[:400],
                    "required_skills": [],
                    "preferred_skills": [],
                    "responsibilities": [],
                    "key_objectives": [],
                    "min_experience_years": 0,
                    "required_languages": [],
                }
            # Ensure title fallback: si el LLM omitió el título o devolvió
            # un placeholder de plantilla, buscar la primera línea real.
            if not parsed.get("title") or _first_real_title(parsed["title"]) == "":
                parsed["title"] = _first_real_title(sanitized)[:100] or "Puesto sin título"

            # Ensure description fallback: if LLM skipped it, use first substantial paragraph
            if not parsed.get("description"):
                paragraphs = [p.strip() for p in sanitized.split("\n\n") if len(p.strip()) > 60]
                parsed["description"] = paragraphs[0][:600] if paragraphs else sanitized[:400]

            # Normalize and deduplicate skills. SIEMPRE devuelve lista
            # (nunca None) — Pydantic rechaza None en campos List[str].
            def _dedup_skills(lst):
                if not lst:
                    return []
                # El LLM (sobre todo cloud) a veces devuelve las skills como un
                # string "Python, SQL, Excel" en lugar de una lista. Sin esto el
                # bucle iteraba CARÁCTER por carácter ('P','y','t',...) y
                # arruinaba el ranking de la vacante en silencio. Lo partimos.
                if isinstance(lst, str):
                    lst = [p.strip() for p in re.split(r"[,;\n]", lst) if p.strip()]
                if not isinstance(lst, list):
                    return []
                seen: set[str] = set()
                out = []
                for s in lst:
                    if not s or not str(s).strip():
                        continue
                    key = str(s).strip().lower()
                    if key not in seen:
                        seen.add(key)
                        out.append(str(s).strip())
                return out

            parsed["required_skills"] = _dedup_skills(parsed.get("required_skills"))
            parsed["preferred_skills"] = _dedup_skills(parsed.get("preferred_skills"))

            # Defaults para campos list que el LLM puede haber devuelto null.
            # Pydantic los rechaza si llegan como None.
            for list_field in ("responsibilities", "key_objectives", "required_languages"):
                if parsed.get(list_field) is None:
                    parsed[list_field] = []

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
        candidate_skills: list,
        job_title: str,
        job_description: str,
        required_skills: list,
        preferred_skills: list,
        min_experience_years: int = 0,
        candidate_experience: list[dict] | None = None,
        candidate_education: list[dict] | None = None,
        candidate_languages: list[dict] | None = None,
        candidate_summary: str | None = None,
        usage_out: Optional[dict] = None,
    ) -> dict:
        """Evalúa el fit candidato-puesto usando razonamiento estructurado del LLM.

        **Principio de minimización de datos (LPDP Perú Art. 6.4 / GDPR Art. 5.1c):**
        Este método **NO recibe ni envía** datos identificatorios del candidato
        (nombre, email, teléfono, DNI, dirección, fecha de nacimiento). El LLM
        evalúa el fit sobre datos estructurados de carrera y educación. La
        identidad del candidato se conserva en la DB de RecruitAI y solo se
        muestra al reclutador en la UI, nunca al LLM externo.

        Devuelve scores por dimensión, recomendación, años de experiencia
        relevante, skills críticas faltantes y una guía de 3 preguntas de
        entrevista.

        Args:
            candidate_skills:     Skills extraídas del CV (lista de strings).
            job_title:            Título del puesto.
            job_description:      Descripción enriquecida del puesto.
            required_skills:      Habilidades obligatorias.
            preferred_skills:     Habilidades deseables.
            min_experience_years: Años mínimos de experiencia exigidos.
            candidate_experience: Lista de dicts con experiencia estructurada
                ``[{cargo, empresa, fecha_inicio, fecha_fin, descripcion}]``.
                Crítico para calcular ``relevant_experience_years`` con fechas
                exactas.
            candidate_education:  Lista de dicts con educación estructurada
                ``[{institution, degree, field_of_study, degree_status,
                start_date, end_date, education_type}]``. Usado para
                ``education_score``.
            candidate_languages:  Lista de dicts con idiomas del candidato
                ``[{idioma, nivel}]``. Usado si la vacante requiere idiomas.
            candidate_summary:    Resumen profesional opcional (sin PII). El
                callsite debe garantizar que no contiene datos identificatorios.

        **No agregar nunca** un parámetro ``candidate_raw_text`` ni similar:
        el CV crudo contiene PII por construcción y violaría el principio de
        minimización. Si se necesita un dato adicional del candidato,
        extraerlo estructuradamente y agregarlo como campo tipado.
        """
        if not await self._is_provider_available():
            return self._fallback_match_scores(candidate_skills, required_skills)

        # Sanitize all user-controlled inputs before injecting into the prompt.
        # This prevents prompt injection from malicious CV content or job field values.
        def _strip_injection(text: str, max_len: int) -> str:
            """Remove control sequences and truncate."""
            if not text:
                return ""
            cleaned = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
            cleaned = re.sub(r'<[^>]{1,60}>', '', cleaned)  # strip html/xml tags
            cleaned = re.sub(r'\[/?INST\]|<<SYS>>|</s>', '', cleaned)
            cleaned = re.sub(r'(?i)(system|assistant|user)\s*:', '', cleaned)
            return cleaned[:max_len].strip()

        def _format_experience_block(entries: list[dict]) -> str:
            """Convierte una lista de experiencias estructuradas a bullets legibles.

            Pasar al modelo bullets con fechas exactas y logros separados:
              - Reduce ~30% los tokens vs raw_text completo (sin headers / formato markdown).
              - Permite cálculo preciso de ``relevant_experience_years`` con fechas reales.
              - Elimina el ruido de extractos del PDF (encabezados de página, separadores).
            """
            if not entries:
                return "(sin experiencia profesional registrada)"
            lines: list[str] = []
            for exp in entries:
                cargo = _strip_injection(str(exp.get("cargo") or ""), 120) or "—"
                empresa = _strip_injection(str(exp.get("empresa") or ""), 120) or "—"
                fi = exp.get("fecha_inicio") or "?"
                ff = exp.get("fecha_fin") or "Presente"
                descripcion = _strip_injection(str(exp.get("descripcion") or ""), 600)
                lines.append(f"- {cargo} @ {empresa} ({fi} → {ff})")
                if descripcion:
                    lines.append(f"  {descripcion}")
            return "\n".join(lines)

        def _format_education_block(entries: list[dict]) -> str:
            """Convierte la educación estructurada a bullets. NO incluye PII:
            instituciones y grados no son datos personales del candidato."""
            if not entries:
                return "(sin formación académica registrada)"
            lines: list[str] = []
            for edu in entries:
                degree = _strip_injection(str(edu.get("degree") or ""), 120) or "—"
                inst = _strip_injection(str(edu.get("institution") or ""), 120) or "—"
                field = _strip_injection(str(edu.get("field_of_study") or ""), 120)
                status = _strip_injection(str(edu.get("degree_status") or ""), 50)
                edu_type = edu.get("education_type") or "educacion"
                fi = edu.get("start_date") or ""
                ff = edu.get("end_date") or ""
                # En Perú, degree_status es crítico (Bachiller vs Titulado vs Colegiado).
                status_suffix = f" — {status}" if status else ""
                type_prefix = "[Cert] " if edu_type == "certificacion" else ""
                field_suffix = f" ({field})" if field else ""
                period = f" ({fi} → {ff})" if fi or ff else ""
                lines.append(f"- {type_prefix}{degree}{field_suffix} @ {inst}{status_suffix}{period}")
            return "\n".join(lines)

        def _format_languages_block(entries: list[dict] | None) -> str:
            """Idiomas declarados por el candidato. No es PII (es competencia)."""
            if not entries:
                return "(no declarados)"
            parts: list[str] = []
            for lang in entries:
                idioma = _strip_injection(str(lang.get("idioma") or ""), 40)
                nivel = _strip_injection(str(lang.get("nivel") or ""), 40)
                if idioma:
                    parts.append(f"{idioma}{(' ' + nivel) if nivel else ''}")
            return ", ".join(parts) if parts else "(no declarados)"

        safe_title = _strip_injection(job_title, 120)
        safe_desc = _strip_injection(job_description, 1200)
        skills_str = (
            ", ".join(
                re.sub(r'[^\w\s\+\#\.\-]', '', s)[:60] for s in candidate_skills[:20]
            )
            if candidate_skills
            else "No disponibles"
        )
        req_str = (
            ", ".join(
                re.sub(r'[^\w\s\+\#\.\-]', '', s)[:60] for s in required_skills[:15]
            )
            if required_skills
            else "No especificadas"
        )
        pref_str = (
            ", ".join(
                re.sub(r'[^\w\s\+\#\.\-]', '', s)[:60] for s in preferred_skills[:10]
            )
            if preferred_skills
            else "No especificadas"
        )
        experience_block = _format_experience_block(candidate_experience or [])
        education_block = _format_education_block(candidate_education or [])
        languages_block = _format_languages_block(candidate_languages)
        safe_summary = _strip_injection(candidate_summary or "", 600)

        # Prompt y system message viven en backend/app/prompts/ — ver
        # match_candidate.md y match_candidate_system.md. La tabla de
        # recomendación determinista (skills/experience cutoffs) está
        # documentada ahí; este código solo inyecta los datos del
        # candidato y la vacante en los slots $variable.
        from app.prompts import render as _render_prompt

        prompt = _render_prompt(
            "match_candidate",
            job_title=safe_title,
            min_experience_years=min_experience_years,
            required_skills=req_str,
            preferred_skills=pref_str,
            job_description=safe_desc,
            candidate_skills=skills_str,
            experience_block=experience_block,
            education_block=education_block,
            languages_block=languages_block,
            candidate_summary=safe_summary or "(no disponible)",
        )
        system_msg = _render_prompt("match_candidate_system")

        try:
            # temperature=0.0 → greedy decoding determinista. Antes era 0.15 y
            # producía scores ligeramente distintos entre runs sobre el mismo CV,
            # rompiendo la confianza del usuario en el ranking.
            # max_tokens=4000: cubre el JSON de salida con margen para thinking
            # de modelos como qwen3 (OLLAMA_THINKING=true). Con 2500, Gemini
            # 2.5 Flash quemaba el presupuesto pensando y truncaba el JSON.
            _t0 = time.perf_counter()
            raw = await self.provider.generate(
                prompt=prompt,
                system_prompt=system_msg,
                json_mode=True,  # cloud: activa response_format JSON (ver extract_resume)
                json_schema=self.MATCH_JSON_SCHEMA,
                temperature=0.0,
                max_tokens=4000,
            )
            self._fill_usage(usage_out, self.provider, int((time.perf_counter() - _t0) * 1000))

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

            # JSON truncado a mitad de camino: json_repair puede rescatar un
            # dict parcial (solo "_razonamiento_previo") y los .get() de abajo
            # rellenarían 50/50/50 silenciosos. Sin skills_score el análisis
            # no sirve — mejor el fallback honesto de overlap.
            if isinstance(result, dict) and "skills_score" not in result:
                logger.warning(
                    f"LLM match JSON incompleto (¿truncado?). Keys: {list(result.keys())[:5]}"
                )
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

            def _to_score(v, default: float = 50.0) -> float:
                # Coacciona el score a float en [0,100] tolerando str ('85') o
                # None. Antes ``max('85', 0)`` lanzaba TypeError y descartaba
                # TODO el análisis IA (explicación, recomendación, guía de
                # entrevista) cayendo al fallback de overlap de skills — sin
                # avisar al reclutador, en una operación de alto riesgo (DS 115).
                try:
                    if v is None or isinstance(v, bool):
                        return default
                    return min(max(float(v), 0.0), 100.0)
                except (TypeError, ValueError):
                    return default

            return {
                "skills_score": _to_score(result.get("skills_score")),
                "experience_score": _to_score(result.get("experience_score")),
                "education_score": _to_score(result.get("education_score")),
                "explanation": str(result.get("explanation", "Perfil analizado por IA."))[:500],
                "recommendation": recommendation,
                "relevant_experience_years": relevant_experience_years,
                "missing_critical_skills": [
                    str(s) for s in result.get("missing_critical_skills", [])
                    if s and isinstance(s, str)
                ][:10],
                "guia_entrevista": guia_entrevista,
            }
        except LLMRateLimitError:
            # Cuota agotada: dejar que la ruta /match decida. El fallback de
            # overlap aquí guardaba puntajes basura en match_results y el
            # caché los daba por buenos en re-análisis posteriores.
            raise
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
    
    async def explain_for_candidate(
        self,
        candidate_name: str,
        job_title: str,
        overall_score: float,
        recommendation: str,
        explanation_internal: str,
        missing_skills: list,
        bonus_skills: list,
        usage_out: Optional[dict] = None,
    ) -> str:
        """Reformula la explicación interna del matching en lenguaje accesible
        dirigido al candidato.

        Cumple el derecho a explicación del Reglamento de IA peruano
        (DS 115-2025-PCM): el candidato puede solicitar saber por qué fue
        evaluado de cierta forma, y la respuesta debe estar en lenguaje claro,
        sin tecnicismos, sin mencionar modelos, prompts ni puntajes técnicos
        internos.

        Tono:
        - Segunda persona ("Tu CV…", "Tu perfil…").
        - Constructivo: si hay brechas, sugerirlas como áreas de desarrollo.
        - Honesto: no inventar fortalezas que no estén en la evaluación.
        - 2-4 párrafos cortos. Sin emojis. Sin lenguaje judgmental.

        Args:
            candidate_name: Nombre del candidato (para personalizar).
            job_title: Título de la vacante.
            overall_score: Puntaje 0-100 (no se le muestra al candidato).
            recommendation: Recomendación interna (no se le muestra textual).
            explanation_internal: Texto del LLM original (puede ser técnico).
            missing_skills: Habilidades requeridas que el CV no muestra.
            bonus_skills: Habilidades extra valoradas que sí tiene.

        Returns:
            Texto plano en español, listo para enviar al candidato.
        """
        first_name = candidate_name.split()[0] if candidate_name else "candidato/a"

        # Sanitiza inputs por si traen prompt injection latente (Layer 1 ya lo
        # validó al ingestar el CV, pero los datos pueden cambiar después).
        explanation_clean = self.sanitize_input(explanation_internal or "")[:1500]
        missing_clean = [self.sanitize_input(s)[:60] for s in (missing_skills or [])[:6]]
        bonus_clean = [self.sanitize_input(s)[:60] for s in (bonus_skills or [])[:6]]

        # Pista cualitativa derivada del score — el número exacto NO va al
        # candidato. Solo le decimos en qué franja general está su perfil.
        if overall_score >= 80:
            fit_hint = "alto encaje con la posición"
        elif overall_score >= 60:
            fit_hint = "encaje parcial con la posición"
        elif overall_score >= 40:
            fit_hint = "encaje limitado con los requisitos actuales"
        else:
            fit_hint = "encaje bajo con los requisitos actuales"

        system_msg = (
            "Eres un asistente de RRHH que comunica el resultado de una "
            "evaluación de CV a un candidato en Perú. Tu respuesta DEBE ser:\n"
            "1. En español neutro, cálido y profesional.\n"
            "2. Sin tecnicismos de IA (no menciones modelos, puntajes, scores, "
            "algoritmos, prompts, ranking).\n"
            "3. En segunda persona, hablando al candidato directamente.\n"
            "4. Entre 2 y 4 párrafos cortos. Sin listas con viñetas. Sin emojis.\n"
            "5. Constructiva: si hay brechas, preséntalas como áreas de "
            "desarrollo, no como fallas.\n"
            "6. Honesta: no inventes fortalezas que no estén en la evaluación.\n"
            "7. Cierre recordando que la decisión final la toma una persona "
            "del equipo de RRHH, no el sistema."
        )

        user_msg = (
            f"Genera la explicación para {first_name}, que postuló al puesto "
            f"de '{job_title}'. La evaluación interna indica {fit_hint}.\n\n"
            f"Resumen interno (NO copiar literal, reformular en lenguaje "
            f"amigable):\n{explanation_clean}\n\n"
            f"Habilidades requeridas que no se identificaron en su CV: "
            f"{', '.join(missing_clean) if missing_clean else 'ninguna relevante'}\n"
            f"Habilidades adicionales valoradas que sí tiene: "
            f"{', '.join(bonus_clean) if bonus_clean else 'ninguna registrada'}\n\n"
            f"Escribe la explicación ahora. Empieza con un saludo a "
            f"{first_name}."
        )

        try:
            _t0 = time.perf_counter()
            response = await self.provider.generate(
                prompt=user_msg,
                system_prompt=system_msg,
                temperature=0.4,  # algo de creatividad para que no suene robótico
                max_tokens=600,
                json_mode=False,
            )
            self._fill_usage(usage_out, self.provider, int((time.perf_counter() - _t0) * 1000))
            text = (response or "").strip()
            # Output scanning: si el LLM emitió algo sospechoso, no lo enviamos
            # — devolvemos el fallback determinístico en su lugar.
            try:
                self.scan_output(text)
            except Exception as scan_exc:
                logger.warning(f"explain_for_candidate output flagged: {scan_exc}")
                return self._fallback_candidate_explanation(first_name, job_title, fit_hint, missing_clean)
            return text or self._fallback_candidate_explanation(first_name, job_title, fit_hint, missing_clean)
        except Exception as exc:
            logger.warning(f"explain_for_candidate failed, using fallback: {exc}")
            return self._fallback_candidate_explanation(first_name, job_title, fit_hint, missing_clean)

    def _fallback_candidate_explanation(
        self, first_name: str, job_title: str, fit_hint: str, missing: list
    ) -> str:
        """Plantilla determinística cuando el LLM no responde — mantiene la
        promesa legal de "derecho a explicación" incluso sin IA disponible.
        """
        intro = (
            f"Hola {first_name},\n\n"
            f"Gracias por postular al puesto de {job_title}. Tras revisar tu "
            f"CV, identificamos un {fit_hint}."
        )
        gaps = (
            f"\n\nAlgunas áreas que el puesto requería y que no encontramos "
            f"explícitamente en tu CV son: {', '.join(missing[:4])}. Esto no "
            f"descarta tu perfil, pero pesa en la comparación con otros "
            f"candidatos que sí las acreditaban."
            if missing else ""
        )
        outro = (
            "\n\nLa decisión final sobre cómo avanzar contigo en este proceso "
            "la toma el equipo de RRHH. Si quieres que reconsideremos algún "
            "punto, escríbenos respondiendo este mensaje."
        )
        return intro + gaps + outro

    async def health_check(self) -> bool:
        """Check if the configured LLM provider is available."""
        return await self._is_provider_available()
    

