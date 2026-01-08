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
    
    # Ollama (local)
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"  # Recommended for local: privacy + free
    
    # LLM Pipeline Strategy
    # Options: "single" (use LLM_PROVIDER for everything) or "pipeline" (use best model for each task)
    LLM_STRATEGY: str = "single"
    
    # Primary LLM Provider for single mode
    # Options: "ollama", "openai", "gemini"
    LLM_PROVIDER: str = "gemini"
    
    # OpenAI - Best for JSON Structured Output
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"  # $0.15/$0.60 per 1M - reliable JSON structuring
    
    # Google Gemini - Best for OCR/Visual processing
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash"  # $0.10/$0.40 per 1M - native PDF/image vision
    
    # Pipeline Mode Settings (when LLM_STRATEGY=pipeline)
    # Stage 1: OCR/Vision - Gemini 2.0 Flash (visual PDF processing)
    # Stage 2: JSON Structuring - GPT-4o-mini (reliable schema compliance)
    PIPELINE_OCR_PROVIDER: str = "gemini"  # For visual PDF/image processing
    PIPELINE_JSON_PROVIDER: str = "openai"  # For final JSON structuring
    
    # Embedding
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    # Security
    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    TOKEN_ENCRYPTION_KEY: Optional[str] = None  # Fernet key for OAuth tokens
    
    # Cloud Sync - OneDrive (Microsoft Graph API)
    ONEDRIVE_CLIENT_ID: Optional[str] = None
    ONEDRIVE_CLIENT_SECRET: Optional[str] = None
    ONEDRIVE_REDIRECT_URI: str = "http://localhost:8000/api/cloud/onedrive/callback"
    
    # Cloud Sync - Google Drive
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/cloud/google-drive/callback"
    
    # Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    
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
