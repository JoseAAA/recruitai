"""
Application Configuration
Uses Pydantic Settings for type-safe environment variables.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


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
    # Model used for candidate matching & scoring — change in .env
    MATCH_MODEL: str = "gemma3:4b"
    # Model used for CV/job-profile data extraction — change in .env
    EXTRACTION_MODEL: str = "gemma3:4b"
    # Embedding model (via Ollama)
    EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # Security
    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
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
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
