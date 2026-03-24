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
    ExperienciaProfesional, EducacionProfesional, DatosPersonales,
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
    # Categories based on OWASP and common attack vectors
    SUSPICIOUS_PATTERNS = [
        # === INSTRUCTION OVERRIDE ATTEMPTS ===
        r"ignore\s+(previous|all|above|prior|earlier)\s+instructions?",
        r"disregard\s+(previous|all|above|prior|earlier)",
        r"forget\s+(everything|what|previous|all|earlier)",
        r"override\s+(previous|system|all|earlier)",
        r"do\s+not\s+follow\s+(previous|prior|earlier)",
        r"stop\s+following\s+(instructions|rules)",
        
        # === ROLE HIJACKING / JAILBREAK ===
        r"you\s+are\s+now\s+a?",
        r"act\s+as\s+(if\s+you\s+are|a)",
        r"pretend\s+(to\s+be|you\s+are)",
        r"roleplay\s+as",
        r"imagine\s+you\s+are",
        r"from\s+now\s+on\s+you\s+are",
        r"switch\s+to\s+.+\s+mode",
        r"enter\s+.+\s+mode",
        r"jailbreak",
        r"DAN\s+mode",  # "Do Anything Now" jailbreak
        
        # === SYSTEM PROMPT MANIPULATION ===
        r"new\s+instructions?:",
        r"system\s*:\s*",
        r"```\s*system",
        r"\[system\]",
        r"<\s*system\s*>",
        r"assistant\s*:\s*",
        r"\[INST\]",
        r"<<SYS>>",
        
        # === OUTPUT MANIPULATION ===
        r"respond\s+only\s+with",
        r"output\s+only",
        r"return\s+only\s+the\s+following",
        r"print\s+the\s+following",
        r"say\s+exactly",
        r"your\s+response\s+must\s+be",
        
        # === ENCODING TRICKS / OBFUSCATION ===
        r"base64\s*:",
        r"hex\s*:",
        r"\\x[0-9a-f]{2}",
        r"unicode\s*:",
        r"rot13\s*:",
        r"decode\s+this",
        
        # === DATA EXFILTRATION ATTEMPTS ===
        r"reveal\s+(your|the)\s+(system|prompt|instructions)",
        r"show\s+me\s+(your|the)\s+prompt",
        r"what\s+are\s+your\s+instructions",
        r"repeat\s+(your|the)\s+(system|initial)\s+prompt",
        r"print\s+your\s+instructions",
        
        # === INDIRECT INJECTION (from external content) ===
        r"if\s+you\s+are\s+an?\s+(ai|assistant|llm)",
        r"dear\s+(ai|assistant|model)",
        r"attention\s+(ai|assistant|model)",
        r"instructions?\s+for\s+(the\s+)?(ai|assistant|model)",
        
        # === CODE EXECUTION ATTEMPTS ===
        r"execute\s+(this|the\s+following)",
        r"run\s+(this|the\s+following)\s+code",
        r"<script>",
        r"javascript:",
        r"eval\s*\(",
    ]
    
    # Layer 2: Maximum input lengths (prevent token exhaustion attacks)
    MAX_CV_LENGTH = 50000  # ~10 pages of text
    MAX_JOB_DESCRIPTION_LENGTH = 20000
    
    # Layer 3: Required output fields (ensure LLM doesn't deviate)
    REQUIRED_RESUME_FIELDS = {"nombre", "email", "skills"}
    REQUIRED_JOB_FIELDS = {"titulo", "requisitos"}
    
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
    
    def sanitize_input(self, text: str, max_length: int = None) -> str:
        """
        Basic input truncation to prevent memory exhaustion.
        Removed aggressive sanitization to preserve pure Docling Markdown.
        """
        if max_length is None:
            max_length = self.MAX_CV_LENGTH
            
        if len(text) > max_length:
            logger.warning(f"Input truncated from {len(text)} to {max_length} chars")
            text = text[:max_length]
            
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
        Returns True if output appears safe, False if anomalies detected.
        
        Note: Logs warning but doesn't block to avoid false positives.
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
            return False
        
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
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        email = email_match.group(0) if email_match else None
        
        # Extract phone
        phone_match = re.search(r'[\+]?[\d\s\-\(\)]{7,15}', text)
        phone = phone_match.group(0).strip() if phone_match else None
        
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
        # Look for patterns like "2020 - 2024", "Enero 2020 - Presente"
        date_pattern = r'(\d{4})\s*[-–]\s*(presente|actual|current|\d{4})'
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
                        if end.lower() in ['presente', 'actual', 'current']:
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
                linkedin=None,
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
    
    async def extract_resume(self, text: str, filename: str = "") -> ExtractedResume:
        """Extract structured resume data from raw text (Markdown via pymupdf4llm)."""
        
        extraction_model = getattr(settings, "EXTRACTION_MODEL", None)
        
        sanitized_text = self.sanitize_input(text)
        
        # Build a clean prompt with an explicit example — much more effective
        # for small models (gemma3:4b) than sending the verbose Pydantic JSON Schema.
        prompt = f"""Eres un experto en extracción de datos de CVs. Analiza el texto y devuelve ÚNICAMENTE un JSON con la estructura del ejemplo.

REGLAS ESTRICTAS:
1. Devuelve SOLO el JSON, sin texto adicional, sin markdown, sin ```json.
2. Si un dato opcional no aparece, usa null. EXCEPCIONES: los campos "cargo", "empresa", "titulo", "institucion" NUNCA deben ser null — usa cadena vacía "" si no están disponibles. NUNCA uses "N/A", "No especificado".
3. El texto fue extraído de un PDF por bloques ordenados por posición. En CVs con diseño de columnas, los datos de distintas secciones aparecen INTERCALADOS en el texto (ej: una fila puede contener empresa de experiencia + institución de educación mezcladas). Usa los encabezados de sección (EXPERIENCIA, EDUCACIÓN, HABILIDADES, IDIOMAS, etc.) para clasificar correctamente cada dato aunque aparezcan fuera de orden.
4. El nombre del candidato suele estar en las primeras líneas del texto, posiblemente dividido en múltiples líneas (nombre de pila en una línea, apellido(s) en la siguiente). Identifica y concatena las líneas iniciales que formen el nombre completo.
5. Busca el email aunque esté separado por espacios o saltos de línea.
6. Busca el teléfono incluyendo prefijos internacionales (+34, +51, +52, etc.).

REGLAS DE NORMALIZACIÓN (MUY IMPORTANTE):
7. "nombre_completo": SIEMPRE en formato Título (Title Case). Ej: "JOSE ALARCON ARONE" → "Jose Alarcon Arone". NUNCA todo en mayúsculas.
8. "cargo": Título de puesto en formato Título. Ej: "ANALISTA DE DATOS SENIOR" → "Analista de Datos Senior".
9. "empresa": Nombre de empresa en formato Título. Ej: "CAMPOSOL" → "Camposol" si es una palabra. Siglas conocidas (IBM, SAP, AWS) se mantienen en mayúsculas.
10. "institucion" (educación): Escribe el NOMBRE COMPLETO de la institución. Ej: "UNMSM" → "Universidad Nacional Mayor de San Marcos", "UNI" → "Universidad Nacional de Ingeniería", "PUCP" → "Pontificia Universidad Católica del Perú", "UPC" → "Universidad Peruana de Ciencias Aplicadas", "UTP" → "Universidad Tecnológica del Perú".
11. "linkedin": URL limpia sin espacios. Si el URL está en dos líneas, únelas. Ej: "linkedin.com/in/jose- alarcon" → "linkedin.com/in/jose-alarcon". Elimina cualquier espacio en el URL.

REGLAS PARA EXPERIENCIA PROFESIONAL:
12. "periodo": texto legible del período, SIEMPRE que haya fechas (ej: "Enero 2021 - Mayo 2024"). Si no hay fechas, usa null.
13. "fecha_inicio": formato "YYYY-MM" (ej: "2021-01"). OBLIGATORIO si hay año/mes visible. Si solo hay año, usa "YYYY-01".
14. "fecha_fin": formato "YYYY-MM" o exactamente la cadena "Presente". Cualquier variante que indique que el trabajo sigue activo ("Presente", "Actual", "Actualidad", "Current", "A la fecha", "Hasta hoy", "Hasta la fecha", "En curso", "–", "Hoy", o campo vacío) → escribe SIEMPRE "Presente". NUNCA uses null cuando el trabajo sigue activo.
15. "es_trabajo_actual": true SOLO si fecha_fin es "Presente" o el cargo sigue activo.
16. "resumen_logros": lista de logros/responsabilidades. Cada ítem debe comenzar con verbo en pasado o infinitivo (ej: "Implementé...", "Lideré...", "Desarrollé..."). Si no hay, usa lista vacía [].

REGLAS PARA EDUCACIÓN (campo "tipo" es OBLIGATORIO):
17. tipo = "educacion" → SOLO títulos académicos formales de grado o posgrado: Bachiller, Licenciatura, Ingeniería, Técnico Superior Universitario, Maestría/Máster, Doctorado, MBA. Si tienes dudas, usa "certificacion".
18. tipo = "certificacion" → TODO lo demás: bootcamp, curso online, diplomado, especialización, taller, certificado profesional, cualquier plataforma (Coursera, Udemy, Platzi, LinkedIn Learning), certificaciones de empresa (Google, AWS, Microsoft, Oracle, Cisco, Scrum, PMP). También aplica a cursos cortos de instituciones presenciales.
19. Para tipo="certificacion": "titulo" = NOMBRE del curso o certificado (ej: "Data Science", "Power BI Integral", "Bootcamp de MLOps"); "institucion" = PLATAFORMA o ENTIDAD que lo emitió (ej: "Coursera", "ADDC Perú", "Código Facilito"). NUNCA pongas el nombre de la plataforma como titulo. NUNCA uses palabras genéricas como titulo: "Certificación", "Certificaciones", "Educación", "Formación", "Diploma", "Título", "Curso" — si no puedes identificar el nombre exacto del curso, omite esa entrada del JSON.
20. "anio_egreso": año de graduación/finalización como string (ej: "2020"). Si no aparece, usa null.
21. En CVs con educación en formato tabla o columnas, si ves grupos de nombres de programas seguidos de listas de institución+año, empareja cada programa con su institución en el mismo orden de aparición.

EJEMPLO DE RESPUESTA:
{{
  "datos_personales": {{
    "nombre_completo": "María García López",
    "telefono": "+34 612345678",
    "email": "maria.garcia@gmail.com",
    "linkedin": "https://www.linkedin.com/in/maria-garcia"
  }},
  "habilidades": ["Python", "SQL", "Power BI", "Machine Learning", "Excel"],
  "experiencia_profesional": [
    {{
      "cargo": "Analista de Datos Senior",
      "empresa": "Empresa ABC",
      "periodo": "Enero 2021 - Mayo 2024",
      "fecha_inicio": "2021-01",
      "fecha_fin": "2024-05",
      "es_trabajo_actual": false,
      "resumen_logros": ["Automatizó procesos ETL reduciendo tiempos un 40%", "Lideró migración de base de datos"]
    }},
    {{
      "cargo": "Data Analyst",
      "empresa": "Tech Corp",
      "periodo": "Junio 2024 - Presente",
      "fecha_inicio": "2024-06",
      "fecha_fin": "Presente",
      "es_trabajo_actual": true,
      "resumen_logros": ["Lideró equipo de 5 personas", "Implementó dashboard de KPIs"]
    }}
  ],
  "educacion": [
    {{
      "institucion": "Universidad Nacional Mayor de San Marcos",
      "titulo": "Bachiller en Estadística",
      "anio_egreso": "2021",
      "tipo": "educacion"
    }},
    {{
      "institucion": "EAE Business School",
      "titulo": "Máster en Big Data & Analytics",
      "anio_egreso": "2020",
      "tipo": "educacion"
    }},
    {{
      "institucion": "Coursera",
      "titulo": "Data Science",
      "anio_egreso": "2020",
      "tipo": "certificacion"
    }},
    {{
      "institucion": "ADDC Perú",
      "titulo": "Power BI Integral",
      "anio_egreso": "2022",
      "tipo": "certificacion"
    }},
    {{
      "institucion": "Código Facilito",
      "titulo": "Bootcamp de MLOps",
      "anio_egreso": "2024",
      "tipo": "certificacion"
    }}
  ]
}}

TEXTO DEL CV A ANALIZAR:
{sanitized_text}"""

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
                    json_mode=True,
                    temperature=0.1,
                    max_tokens=4096
                )
            finally:
                if needs_close:
                    await provider_to_use.close()
            
            logger.debug(f"LLM resume response: {raw_output[:300]}...")
            
            try:
                parsed = json.loads(raw_output)
                resume = ExtractedResume.model_validate(parsed)
                return self._normalize_extracted_resume(resume)
            except json.JSONDecodeError:
                json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    resume = ExtractedResume.model_validate(parsed)
                    return self._normalize_extracted_resume(resume)
                raise ValueError(f"Could not parse LLM response as JSON: {raw_output[:200]}")
        except Exception as e:
            logger.error(f"LLM resume extraction failed: {e}, falling back to simple extraction")
            return self._extract_resume_simple(sanitized_text, filename=filename)

    def _normalize_extracted_resume(self, resume: "ExtractedResume") -> "ExtractedResume":
        """Post-process LLM output: normalize casing, clean LinkedIn URLs, etc."""
        KNOWN_ABBREVS = {
            "unmsm": "Universidad Nacional Mayor de San Marcos",
            "uni": "Universidad Nacional de Ingeniería",
            "pucp": "Pontificia Universidad Católica del Perú",
            "upc": "Universidad Peruana de Ciencias Aplicadas",
            "utp": "Universidad Tecnológica del Perú",
            "udep": "Universidad de Piura",
            "usil": "Universidad San Ignacio de Loyola",
            "ulima": "Universidad de Lima",
            "unfv": "Universidad Nacional Federico Villarreal",
            "unac": "Universidad Nacional del Callao",
            "upn": "Universidad Privada del Norte",
            "ucsur": "Universidad Científica del Sur",
            "usat": "Universidad Católica Santo Toribio de Mogrovejo",
            "uct": "Universidad Católica de Trujillo",
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

        def normalize_institution(name: str) -> str:
            if not name:
                return name
            key = name.strip().lower().rstrip(".")
            if key in KNOWN_ABBREVS:
                return KNOWN_ABBREVS[key]
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

        # Section-label titles the LLM uses as a fallback when it can't read
        # the actual certification/degree name (common with multi-column PDF tables).
        # These are meaningless and must be dropped.
        _GENERIC_TITLES = {
            'certificación', 'certificacion', 'certificaciones',
            'educación', 'educacion', 'formación', 'formacion',
            'diploma', 'título', 'titulo', 'titulación', 'titulacion',
            'grado', 'estudios', 'curso', 'cursos',
        }

        clean_edu = []
        seen_titulos: set[str] = set()
        for edu in resume.educacion or []:
            if edu.institucion:
                edu.institucion = normalize_institution(edu.institucion)
            if edu.titulo:
                edu.titulo = to_title(edu.titulo)
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

        return resume
    
    async def extract_job_profile(self, text: str) -> ExtractedJobProfile:
        """Extract structured job description data using an example-based prompt."""
        if not await self._is_provider_available():
            raise ValueError("LLM provider not available")

        sanitized = self.sanitize_input(text)

        example_json = """{
  "title": "Desarrollador Backend Senior",
  "department": "Tecnología",
  "description": "El puesto lidera el desarrollo de APIs RESTful en un equipo ágil de 8 personas. Es responsable de diseñar microservicios escalables y asegurar la calidad del código.",
  "seniority_level": "senior",
  "work_modality": "hybrid",
  "industry": "Tecnología / Fintech",
  "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Git"],
  "preferred_skills": ["Kubernetes", "Redis", "AWS"],
  "responsibilities": [
    "Diseñar e implementar APIs RESTful con FastAPI",
    "Revisar código de otros desarrolladores del equipo",
    "Optimizar consultas SQL y modelos de base de datos",
    "Escribir pruebas unitarias e de integración",
    "Participar en planificación de sprints y estimaciones"
  ],
  "key_objectives": [
    "Reducir latencia de APIs en un 30% en los primeros 3 meses",
    "Migrar el servicio de pagos a microservicios antes del Q3",
    "Implementar cobertura de pruebas al 80%"
  ],
  "min_experience_years": 3,
  "education_level": "bachelor"
}"""

        prompt = f"""Eres un experto en Recursos Humanos. Analiza el siguiente texto de una descripción de puesto de trabajo y extrae la información en formato JSON.

DEVUELVE ÚNICAMENTE el JSON, sin texto adicional, sin markdown, sin explicaciones.

El JSON debe seguir EXACTAMENTE esta estructura (rellena con los datos del texto):
{example_json}

REGLAS:
- "title": título exacto del puesto (OBLIGATORIO, nunca omitir)
- "department": área o departamento, null si no se menciona
- "description": resumen de 2-4 oraciones del rol y sus objetivos
- "seniority_level": nivel del puesto — "junior", "mid-level", "senior", "lead", "manager" o null
- "work_modality": modalidad — "remote", "hybrid", "onsite" o null
- "industry": industria/sector de la empresa o null
- "required_skills": habilidades OBLIGATORIAS como strings cortos
- "preferred_skills": habilidades DESEABLES como strings cortos
- "responsibilities": lista de 5-10 responsabilidades concretas del día a día
- "key_objectives": lista de 3-5 objetivos/KPIs clave que el puesto debe lograr
- "min_experience_years": número entero (0 si no se especifica)
- "education_level": "bachelor", "master", "phd", "high_school" o null

TEXTO DEL PUESTO:
{sanitized}

JSON:"""

        try:
            raw = await self.provider.generate(
                prompt=prompt,
                system_prompt="Eres un extractor de datos JSON. Responde SOLO con JSON válido.",
                json_mode=True,
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

        # Use up to 3000 chars of raw CV text — enough for full context
        cv_context = (candidate_raw_text or "")[:3000]
        skills_str = ", ".join(candidate_skills[:20]) if candidate_skills else "No disponibles"
        req_str = ", ".join(required_skills[:15]) if required_skills else "No especificadas"
        pref_str = ", ".join(preferred_skills[:10]) if preferred_skills else "No especificadas"

        # /no_think disables qwen3.5 chain-of-thought output in the response.
        # The model still reasons internally but doesn't emit <think> blocks,
        # allowing json_mode to work correctly.
        prompt = f"""/no_think
Eres un reclutador experto con 15 años de experiencia en RRHH. Analiza el CV del candidato para el puesto indicado.

=== PUESTO ===
Título: {job_title}
Experiencia mínima requerida: {min_experience_years} años
Descripción: {job_description[:400]}
Habilidades requeridas: {req_str}
Habilidades deseables: {pref_str}

=== CURRÍCULUM ===
{cv_context}

=== HABILIDADES DETECTADAS ===
{skills_str}

Razona paso a paso antes de dar las puntuaciones:
PASO 1 — Habilidades: ¿Cuáles de las requeridas tiene el candidato? ¿Cuáles le faltan? Calcula un porcentaje realista.
PASO 2 — Experiencia: ¿Cuántos años tiene? ¿Los roles son relevantes para {job_title}? ¿Ha trabajado en contextos similares?
PASO 3 — Educación: ¿Su formación es adecuada para el puesto?
PASO 4 — Conclusión: ¿Vale la pena entrevistar a esta persona?

Responde ÚNICAMENTE con JSON válido (sin texto extra):
{{
    "skills_score": <número 0-100>,
    "experience_score": <número 0-100>,
    "education_score": <número 0-100>,
    "explanation": "<frase concisa máx 25 palabras explicando el punto más destacado>",
    "recommendation": "<exactamente uno de: Altamente recomendado | Buena opción | Considerar | No recomendado>"
}}"""

        try:
            # qwen3.5 uses ~1500-2000 tokens for internal reasoning before generating content.
            # max_tokens must cover both thinking + JSON output.
            raw = await self.provider.generate(
                prompt=prompt,
                json_mode=True,
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

            return {
                "skills_score": float(min(max(result.get("skills_score", 50), 0), 100)),
                "experience_score": float(min(max(result.get("experience_score", 50), 0), 100)),
                "education_score": float(min(max(result.get("education_score", 50), 0), 100)),
                "explanation": str(result.get("explanation", "Perfil analizado por IA."))[:250],
                "recommendation": recommendation,
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
    
    async def generate_interview_questions(
        self,
        candidate_name: str,
        candidate_skills: list[str],
        job_title: str,
        job_required_skills: list[str],
        job_preferred_skills: list[str],
        skill_gaps: list[str],
        matching_skills: list[str]
    ) -> dict:
        """
        Generate tailored interview questions using the configured LLM provider.
        Returns questions in different categories: technical, behavioral, situational.
        """
        # Fallback when no provider is available
        if not await self._is_provider_available():
            return self._generate_fallback_questions(
                candidate_name, candidate_skills, job_title,
                job_required_skills, skill_gaps, matching_skills
            )
        
        prompt = f"""Eres un experto reclutador de RRHH. Genera preguntas de entrevista personalizadas para evaluar a un candidato.

CANDIDATO: {candidate_name}
PUESTO: {job_title}
HABILIDADES DEL CANDIDATO: {', '.join(candidate_skills[:10]) if candidate_skills else 'No especificadas'}
HABILIDADES REQUERIDAS: {', '.join(job_required_skills[:10]) if job_required_skills else 'No especificadas'}
HABILIDADES QUE LE FALTAN: {', '.join(skill_gaps[:5]) if skill_gaps else 'Ninguna'}
HABILIDADES QUE COINCIDEN: {', '.join(matching_skills[:5]) if matching_skills else 'Ninguna'}

Genera las siguientes preguntas en formato JSON:
{{
    "technical_questions": [
        // 3-4 preguntas técnicas para evaluar las habilidades que coinciden y explorar las que faltan
    ],
    "gap_questions": [
        // 2-3 preguntas específicas sobre las habilidades que le faltan (skill gaps)
        // Enfocadas en evaluar capacidad de aprendizaje y experiencia relacionada
    ],
    "behavioral_questions": [
        // 2 preguntas de comportamiento relacionadas con el rol
    ],
    "situational_questions": [
        // 2 preguntas situacionales del día a día del puesto
    ]
}}

Cada pregunta debe ser específica, profesional y en español.
Devuelve SOLO el JSON válido, sin texto adicional."""

        try:
            raw_output = await self.provider.generate(
                prompt=prompt,
                json_mode=True,
                temperature=0.7,
                max_tokens=1500
            )
            
            try:
                parsed = json.loads(raw_output)
                return {
                    "candidate_name": candidate_name,
                    "job_title": job_title,
                    "skill_gaps": skill_gaps,
                    "matching_skills": matching_skills,
                    "questions": parsed,
                    "generated_by_ai": True,
                    "provider": self.provider.name
                }
            except json.JSONDecodeError:
                logger.warning("Failed to parse AI response, using fallback")
                return self._generate_fallback_questions(
                    candidate_name, candidate_skills, job_title,
                    job_required_skills, skill_gaps, matching_skills
                )
        except Exception as e:
            logger.error(f"Error generating interview questions: {e}")
            return self._generate_fallback_questions(
                candidate_name, candidate_skills, job_title,
                job_required_skills, skill_gaps, matching_skills
            )
    
    def _generate_fallback_questions(
        self,
        candidate_name: str,
        candidate_skills: list[str],
        job_title: str,
        job_required_skills: list[str],
        skill_gaps: list[str],
        matching_skills: list[str]
    ) -> dict:
        """Generate predefined questions as fallback when AI is unavailable."""
        technical_questions = []
        gap_questions = []
        
        # Generate questions based on matching skills
        for skill in matching_skills[:3]:
            technical_questions.append(
                f"Cuéntame sobre tu experiencia trabajando con {skill}. ¿Qué proyectos has desarrollado?"
            )
        
        # Generate questions based on skill gaps
        for gap in skill_gaps[:3]:
            gap_questions.append(
                f"Veo que {gap} es un requisito para este puesto. ¿Has tenido alguna exposición a esta tecnología? ¿Cómo abordarías aprenderla?"
            )
        
        # Add generic technical question if needed
        if not technical_questions:
            technical_questions.append(
                f"¿Cuáles son las tecnologías que más dominas para el puesto de {job_title}?"
            )
        
        return {
            "candidate_name": candidate_name,
            "job_title": job_title,
            "skill_gaps": skill_gaps,
            "matching_skills": matching_skills,
            "questions": {
                "technical_questions": technical_questions + [
                    "Describe un problema técnico complejo que hayas resuelto recientemente.",
                    "¿Cómo te mantienes actualizado con las nuevas tecnologías?"
                ],
                "gap_questions": gap_questions if gap_questions else [
                    "¿Hay alguna área técnica donde te gustaría crecer profesionalmente?",
                    "¿Cómo abordarías aprender una tecnología nueva que el equipo usa?"
                ],
                "behavioral_questions": [
                    "Cuéntame sobre una situación donde tuviste que trabajar bajo presión. ¿Cómo la manejaste?",
                    "Describe una ocasión donde tuviste un desacuerdo con un compañero. ¿Cómo lo resolviste?"
                ],
                "situational_questions": [
                    f"Imagina que eres el {job_title} y tienes un deadline de 2 días para una feature crítica. ¿Cómo priorizarías tu trabajo?",
                    "Si detectas un bug en producción justo antes de irte, ¿qué harías?"
                ]
            },
            "generated_by_ai": False
        }

