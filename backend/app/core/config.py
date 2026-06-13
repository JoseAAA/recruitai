"""
Application Configuration
Uses Pydantic Settings for type-safe environment variables.
"""
import logging
from functools import lru_cache
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://recruitai:recruitai_secret@localhost:5432/recruitai_db"
    
    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    
    # Ollama (local Edge AI)
    LLM_PROVIDER: str = "ollama"
    OLLAMA_HOST: str = "http://localhost:11434"

    # ── Único punto de configuración de modelo ─────────────────────────────
    # Cambia SOLO OLLAMA_MODEL en .env para cambiar el modelo de IA.
    # MATCH_MODEL y EXTRACTION_MODEL se sincronizan automáticamente.
    #
    # Modelos normales: gemma3:4b, llama3.2:3b, mistral:7b
    # Modelos thinking: qwen3:4b, deepseek-r1:7b  → también pon OLLAMA_THINKING=true
    # ──────────────────────────────────────────────────────────────────────
    OLLAMA_MODEL: str = "gemma3:4b"
    OLLAMA_THINKING: bool = False   # True → permite razonamiento interno (qwen3, deepseek-r1)

    # Tamaño de ventana de contexto que se le pide a Ollama por request (tokens).
    # Default de Ollama es 2048 — insuficiente para CVs: un CV de 50.000 chars
    # son ~12.500 tokens y se trunca silenciosamente desde el INICIO del prompt
    # (se pierden los datos de contacto que están en la cabecera del CV).
    # gemma3:4b soporta nativamente 128k. 16384 cubre prompt + schema + CV típico.
    # KV cache crece lineal con num_ctx → más VRAM. Bajar a 8192 si hay OOM.
    OLLAMA_NUM_CTX: int = 16384

    # Caracteres del CV que se le pasan al LLM durante el matching contra la vacante.
    # Antes estaba hardcodeado en 5000 (~1.250 tokens) → el modelo solo veía el 30-40%
    # de un CV típico, perdiendo experiencias y certificaciones relevantes.
    # 18000 chars (~4.500 tokens) es lo que cabe junto al prompt del matcher en num_ctx=16384.
    LLM_MATCH_CV_CONTEXT: int = 18000

    # Concurrencia de scoring LLM en el matching. Antes hardcoded a 3.
    # Debe ser <= OLLAMA_NUM_PARALLEL en docker-compose.yml para no encolar.
    # Con num_ctx=16384 cada slot consume ~1 GB de KV cache → en RTX 3060 6GB
    # bajamos a 2 para evitar OOM. Si subes la VRAM o bajas num_ctx, sube esto también.
    LLM_MATCH_CONCURRENCY: int = 2

    # Derivados — no editar en .env, se sincronizan desde OLLAMA_MODEL
    MATCH_MODEL: str = ""
    EXTRACTION_MODEL: str = ""

    # ── Embeddings (servicio TEI separado, INDEPENDIENTE del LLM) ─────────
    # Patrón "separation of inference services": embeddings y LLM corren en
    # contenedores distintos. Cambiar LLM_PROVIDER no afecta a embeddings.
    # Ver docker-compose.yml servicio ``embeddings``.
    EMBEDDINGS_HOST: str = "http://embeddings:8080"
    # Snowflake/snowflake-arctic-embed-m-v2.0:
    #   - 768 dim (mismo que la colección Qdrant actual — no re-indexar)
    #   - Apache 2.0, multilingüe (ES/EN/DE/FR/IT)
    #   - 305M params, ~1.2 GB en disco, ~600 MB RAM
    # Para upgrade a calidad máxima (futuro): BAAI/bge-m3 (1024 dim, requiere
    # re-indexar Qdrant). Sin urgencia — arctic-embed-m ya es top tier ES.
    EMBEDDING_MODEL: str = "Snowflake/snowflake-arctic-embed-m-v2.0"
    
    # Security
    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # ── Proveedores LLM cloud ─────────────────────────────────────────────
    # API keys (solo se requieren si LLM_PROVIDER apunta al proveedor).
    # Si configuras LLM_PROVIDER=<cloud> pero falta la key, el backend levanta
    # ValueError al arranque (en producción) o warning (en development).
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # Modelos por defecto de cada proveedor cloud — el ingeniero puede
    # cambiarlos en .env sin tocar código.
    # OJO lifecycle Google: gemini-2.0-flash fue APAGADO el 01-jun-2026 (toda
    # llamada devuelve error). gemini-2.5-flash se retira ~16-oct-2026 →
    # migrar a gemini-3.5-flash cuando Google avise. Free tier ~1.5k req/día,
    # 15 req/min (Google los recorta sin aviso — verificar en
    # https://ai.google.dev/gemini-api/docs/rate-limits).
    GEMINI_MODEL: str = "gemini-2.5-flash"
    # Marcapasos free tier: segundos mínimos entre llamadas a Gemini. La cuota
    # es por MINUTO; sin espaciado, el matching en lote provoca tormenta de
    # 429+reintentos (10 candidatos = 12 min). Con 6s ≈ 10 req/min seguras.
    # Poner 0 si tienes tier pagado.
    GEMINI_MIN_REQUEST_INTERVAL: float = 6.0
    OPENAI_MODEL: str = "gpt-4o-mini"             # Calidad/precio óptimo
    # Llama 3.3 70B: estable con structured output JSON complejo (job/resume).
    # Probado Llama 4 Scout (17b-16e-instruct) — más barato pero INESTABLE:
    # devuelve JSON malformado que ni json-repair recupera, especialmente
    # con prompts largos y schemas extensos. Re-evaluar cuando salga la
    # versión refinada de Scout o Llama 5.
    GROQ_MODEL:   str = "llama-3.3-70b-versatile"

    # Privacy & LPDP Perú Compliance
    ENCRYPTION_KEY: Optional[str] = None
    # PII_MASKING_ENABLED se auto-deriva de LLM_PROVIDER:
    #   ollama → False (datos nunca salen, no hay nada que enmascarar)
    #   gemini/openai/groq → True (cloud, hay que enmascarar antes de enviar)
    # El usuario puede sobreescribir explícitamente con PII_MASKING_ENABLED=false
    # en .env si tiene una razón. None = "auto, no especificado".
    PII_MASKING_ENABLED: Optional[bool] = None
    DATA_RETENTION_DAYS: int = 730
    
    # Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 10
    RATE_LIMIT_UPLOAD_PER_MINUTE: int = 10

    # Default user credentials (override in production via env vars)
    ADMIN_INITIAL_PASSWORD: str = "change-me-on-first-run"
    RECRUITER_INITIAL_PASSWORD: str = "change-me-on-first-run"

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    @model_validator(mode="after")
    def sync_ollama_model(self) -> "Settings":
        """Sincroniza MATCH_MODEL y EXTRACTION_MODEL desde OLLAMA_MODEL.

        Si MATCH_MODEL o EXTRACTION_MODEL no están definidos en .env (quedan ""),
        se copian desde OLLAMA_MODEL. Esto permite cambiar el modelo en un solo lugar.
        Si en algún momento se necesitan modelos distintos para extracción y matching,
        basta con definirlos explícitamente en .env y este validator los respeta.
        """
        if not self.MATCH_MODEL:
            self.MATCH_MODEL = self.OLLAMA_MODEL
        if not self.EXTRACTION_MODEL:
            self.EXTRACTION_MODEL = self.OLLAMA_MODEL
        return self

    @model_validator(mode="after")
    def validate_llm_provider_and_pii(self) -> "Settings":
        """Coordina LLM_PROVIDER, sus API keys y PII masking en un solo paso.

        Reglas (en orden de aplicación):

        1. **API key obligatoria para proveedores cloud.**
           Si ``LLM_PROVIDER`` es ``gemini``, ``openai`` o ``groq``, la API key
           correspondiente DEBE estar en ``.env``. Antes hacíamos fallback
           silencioso a Ollama — eso causaba bugs confusos donde el ingeniero
           creía estar usando la API y en realidad seguía en local.

        2. **PII masking auto-derivado.**
           Si el usuario no especificó ``PII_MASKING_ENABLED`` explícitamente,
           se activa automáticamente para proveedores cloud (LPDP Perú: no
           enviar datos personales a USA sin enmascarar) y se desactiva para
           Ollama (datos nunca salen, masking sería overhead inútil).

        3. **ENCRYPTION_KEY requerida si PII masking está activo.**
           El masker usa Fernet AES-256 para encriptar el mapeo reversible.
           Sin clave no puede operar.
        """
        provider = (self.LLM_PROVIDER or "ollama").lower()
        valid = {"ollama", "gemini", "openai", "groq"}
        if provider not in valid:
            raise ValueError(
                f"LLM_PROVIDER='{self.LLM_PROVIDER}' no es válido. "
                f"Opciones: {sorted(valid)}."
            )

        # Regla 1 — API key obligatoria para cloud (solo en producción; en dev
        # dejamos que falle al primer request para que el ingeniero pueda
        # iterar sin reiniciar todo el contenedor).
        cloud_keys = {
            "gemini": ("GEMINI_API_KEY", self.GEMINI_API_KEY),
            "openai": ("OPENAI_API_KEY", self.OPENAI_API_KEY),
            "groq":   ("GROQ_API_KEY",   self.GROQ_API_KEY),
        }
        if provider in cloud_keys:
            key_name, key_value = cloud_keys[provider]
            if not key_value:
                msg = (
                    f"LLM_PROVIDER='{provider}' pero {key_name} no está en .env. "
                    f"Configúrala o cambia LLM_PROVIDER=ollama."
                )
                if self.ENVIRONMENT == "production":
                    raise ValueError(msg)
                logger.warning(msg)

        # Regla 2 — PII masking auto-derivado
        if self.PII_MASKING_ENABLED is None:
            self.PII_MASKING_ENABLED = provider != "ollama"
            if self.PII_MASKING_ENABLED:
                logger.info(
                    f"PII masking activado automáticamente "
                    f"(LLM_PROVIDER={provider}, datos van a la nube)"
                )

        # Regla 3 — encryption key requerida si PII masking activo
        if self.PII_MASKING_ENABLED and not self.ENCRYPTION_KEY:
            msg = (
                "PII_MASKING_ENABLED=true requiere ENCRYPTION_KEY en .env. "
                "Generar con: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
            if self.ENVIRONMENT == "production":
                raise ValueError(msg)
            logger.warning(msg)

        return self

    @model_validator(mode="after")
    def check_insecure_defaults(self) -> "Settings":
        # In production we still HARD-FAIL so a misconfigured deploy can't run.
        # In development (default) we keep the startup log clean — the warning
        # was noisy on every container restart and obscured real issues.
        # See README "Producción" section for guidance on rotating secrets.
        insecure_secrets = [
            ("JWT_SECRET", self.JWT_SECRET, "change-this-in-production"),
            ("ADMIN_INITIAL_PASSWORD", self.ADMIN_INITIAL_PASSWORD, "change-me-on-first-run"),
            ("RECRUITER_INITIAL_PASSWORD", self.RECRUITER_INITIAL_PASSWORD, "change-me-on-first-run"),
        ]
        offenders = [name for name, value, default in insecure_secrets if value == default]
        if offenders and self.ENVIRONMENT == "production":
            raise ValueError(
                f"Insecure default values detected for: {', '.join(offenders)}. "
                f"Set them in your .env before deploying."
            )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
