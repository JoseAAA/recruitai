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

    # Derivados — no editar en .env, se sincronizan desde OLLAMA_MODEL
    MATCH_MODEL: str = ""
    EXTRACTION_MODEL: str = ""

    # Embedding model (via Ollama) — raramente necesita cambiar
    EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # Security
    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Cloud LLM API Keys (optional — only needed if LLM_PROVIDER != ollama)
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # Privacy & LPDP Perú Compliance
    ENCRYPTION_KEY: Optional[str] = None
    PII_MASKING_ENABLED: bool = False  # Enable only if sending data to cloud APIs
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
    def check_insecure_defaults(self) -> "Settings":
        insecure_secrets = [
            ("JWT_SECRET", self.JWT_SECRET, "change-this-in-production"),
            ("ADMIN_INITIAL_PASSWORD", self.ADMIN_INITIAL_PASSWORD, "change-me-on-first-run"),
            ("RECRUITER_INITIAL_PASSWORD", self.RECRUITER_INITIAL_PASSWORD, "change-me-on-first-run"),
        ]
        offenders = [name for name, value, default in insecure_secrets if value == default]
        if offenders:
            msg = f"⚠️  Insecure default values detected for: {', '.join(offenders)}. Set them in your .env file."
            if self.ENVIRONMENT == "production":
                raise ValueError(msg)
            else:
                logger.warning(msg)
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
