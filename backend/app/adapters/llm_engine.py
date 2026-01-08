"""
LLM Engine Adapter
Handles communication with LLM providers for structured data extraction.
Supports multiple providers: Ollama (local), OpenAI, Gemini.
Includes fallback for when no LLM is available.
"""
import json
import logging
import re
from typing import Optional, Type, TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.domain.models import ExtractedJobProfile, ExtractedResume, ExperienceEntry, EducationEntry
from app.adapters.llm_providers import get_provider, LLMProvider

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
    # ===========================================
    
    # Layer 1: Suspicious patterns (regex-based detection)
    SUSPICIOUS_PATTERNS = [
        # Instruction override attempts
        r"ignore\s+(previous|all|above|prior)\s+instructions?",
        r"disregard\s+(previous|all|above|prior)",
        r"forget\s+(everything|what|previous|all)",
        r"override\s+(previous|system|all)",
        # Role hijacking
        r"you\s+are\s+now\s+a?",
        r"act\s+as\s+(if\s+you\s+are|a)",
        r"pretend\s+(to\s+be|you\s+are)",
        r"roleplay\s+as",
        # System prompt manipulation
        r"new\s+instructions?:",
        r"system\s*:\s*",
        r"```\s*system",
        r"\[system\]",
        r"<\s*system\s*>",
        # Output manipulation
        r"respond\s+only\s+with",
        r"output\s+only",
        r"return\s+only\s+the\s+following",
        # Encoding tricks
        r"base64\s*:",
        r"hex\s*:",
        r"\\x[0-9a-f]{2}",
    ]
    
    # Layer 2: Maximum input lengths (prevent token exhaustion attacks)
    MAX_CV_LENGTH = 50000  # ~10 pages of text
    MAX_JOB_DESCRIPTION_LENGTH = 20000
    
    # Layer 3: Required output fields (ensure LLM doesn't deviate)
    REQUIRED_RESUME_FIELDS = {"nombre", "email", "skills"}
    REQUIRED_JOB_FIELDS = {"titulo", "requisitos"}
    
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._provider: Optional[LLMProvider] = None
        self._provider_available: Optional[bool] = None
        # Legacy support
        self.base_url = settings.OLLAMA_HOST
        self.model = settings.OLLAMA_MODEL
        self._client = client
    
    @property
    def provider(self) -> LLMProvider:
        """Get the configured LLM provider."""
        if self._provider is None:
            self._provider = get_provider()
        return self._provider
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client
    
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
    
    # Legacy method for backwards compatibility
    async def _is_ollama_available(self) -> bool:
        """Legacy method - now checks configured provider."""
        return await self._is_provider_available()
    
    def sanitize_input(self, text: str, max_length: int = None) -> str:
        """
        Multi-layer input sanitization for prompt injection prevention.
        
        Layer 1: Remove control characters
        Layer 2: Check for suspicious patterns
        Layer 3: Enforce length limits
        """
        if max_length is None:
            max_length = self.MAX_CV_LENGTH
        
        # Layer 1: Remove control characters (except newlines/tabs)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        # Layer 2: Pattern-based detection
        text_lower = text.lower()
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, text_lower):
                logger.warning(f"Prompt injection detected: {pattern}")
                raise PromptInjectionError(f"Contenido sospechoso detectado en el documento")
        
        # Layer 3: Length limit enforcement
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
    
    def _extract_resume_simple(self, text: str) -> ExtractedResume:
        """Simple regex-based resume extraction as fallback."""
        text_lower = text.lower()
        lines = text.split('\n')
        
        # Try to extract name from first non-empty line
        full_name = "Candidato Desconocido"
        for line in lines[:5]:
            line = line.strip()
            if line and len(line) > 3 and len(line.split()) <= 4:
                # Likely a name
                full_name = line.title()
                break
        
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
        
        # Create summary from first 500 chars
        summary = text[:500].replace('\n', ' ').strip()
        
        return ExtractedResume(
            full_name=full_name,
            email=email,
            phone=phone,
            summary=summary,
            skills=list(set(found_skills)),
            experience=[],
            education=[]
        )
    
    async def extract_structured(
        self,
        text: str,
        schema: Type[T],
        system_prompt: str
    ) -> T:
        """Extract structured data from text using configured LLM provider."""
        sanitized_text = self.sanitize_input(text)
        
        # Check if provider is available
        if not await self._is_provider_available():
            logger.info("LLM provider not available, using simple extraction")
            if schema == ExtractedResume:
                return self._extract_resume_simple(sanitized_text)
            else:
                raise ValueError("Fallback not implemented for this schema")
        
        schema_json = schema.model_json_schema()
        
        full_prompt = f"""{system_prompt}

Extract information from the following document and return it as valid JSON matching this schema:
{json.dumps(schema_json, indent=2)}

<document>
{sanitized_text}
</document>

Return ONLY valid JSON, no additional text or explanation."""
        
        try:
            # Use the configured provider
            raw_output = await self.provider.generate(
                prompt=full_prompt,
                json_mode=True,
                temperature=0.1,
                max_tokens=2000
            )
            
            logger.debug(f"LLM response from {self.provider.name}: {raw_output[:200]}...")
            
            try:
                parsed = json.loads(raw_output)
                return schema.model_validate(parsed)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM output as JSON: {e}")
                json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    return schema.model_validate(parsed)
                raise ValueError(f"Could not parse LLM response as JSON: {raw_output[:200]}")
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}, falling back to simple extraction")
            if schema == ExtractedResume:
                return self._extract_resume_simple(sanitized_text)
            raise
    
    async def extract_resume(self, text: str) -> ExtractedResume:
        """Extract structured resume data from raw text."""
        system_prompt = """You are an expert HR assistant specialized in parsing resumes/CVs.
Extract all relevant information accurately. 
For dates, use YYYY-MM-DD format.
For skills, list both technical and soft skills separately.
If information is not present, use null or empty arrays."""
        
        return await self.extract_structured(text, ExtractedResume, system_prompt)
    
    async def extract_job_profile(self, text: str) -> ExtractedJobProfile:
        """Extract structured job description data."""
        system_prompt = """You are an expert HR assistant specialized in parsing job descriptions.
Extract the key requirements and qualifications.
Distinguish between required skills (must-have) and preferred skills (nice-to-have).
Estimate minimum years of experience if mentioned."""
        
        return await self.extract_structured(text, ExtractedJobProfile, system_prompt)
    
    async def generate_match_explanation(
        self,
        candidate_summary: str,
        job_description: str,
        scores: dict
    ) -> str:
        """Generate a human-readable match explanation."""
        if not await self._is_ollama_available():
            skills_score = scores.get('skills_score', 0)
            if skills_score >= 70:
                return "Candidato con buen perfil técnico que coincide con los requisitos del puesto."
            elif skills_score >= 50:
                return "Candidato con potencial que cumple algunos de los requisitos básicos."
            else:
                return "Candidato que podría requerir desarrollo adicional para el puesto."
        
        prompt = f"""You are an HR advisor. Given the following candidate summary and job requirements, 
explain in 2-3 sentences why this candidate might be a good fit (or not).
Be specific and reference actual skills/experience mentioned.

Candidate Summary:
{candidate_summary[:500]}

Job Requirements:
{job_description[:500]}

Match Scores:
- Skills: {scores.get('skills_score', 0):.0f}%
- Experience: {scores.get('experience_score', 0):.0f}%
- Education: {scores.get('education_score', 0):.0f}%

Provide a brief, professional assessment:"""
        
        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 200,
                }
            }
        )
        response.raise_for_status()
        
        return response.json().get("response", "").strip()
    
    async def health_check(self) -> bool:
        """Check if Ollama is available."""
        return await self._is_ollama_available()
    
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
        Generate tailored interview questions based on candidate's skill gaps.
        Returns questions in different categories: technical, behavioral, situational.
        """
        # Fallback questions when Ollama is not available
        if not await self._is_ollama_available():
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
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 1500,
                    }
                }
            )
            response.raise_for_status()
            
            result = response.json()
            raw_output = result.get("response", "{}")
            
            try:
                parsed = json.loads(raw_output)
                return {
                    "candidate_name": candidate_name,
                    "job_title": job_title,
                    "skill_gaps": skill_gaps,
                    "matching_skills": matching_skills,
                    "questions": parsed,
                    "generated_by_ai": True
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

