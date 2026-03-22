"""
Admin API Routes - System Settings Management
Only accessible by users with admin role.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.db.models import SystemSettingDB
from app.api.routes.auth import get_current_active_user, UserResponse
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ============ Schemas ============

class SettingResponse(BaseModel):
    key: str
    value: str
    description: Optional[str] = None
    updated_at: Optional[datetime] = None


class SettingsUpdateRequest(BaseModel):
    """Request to update multiple settings at once."""
    settings: Dict[str, str]


class ApiKeyStatus(BaseModel):
    """Status of API key configuration (without exposing the actual key)."""
    provider: str
    configured: bool
    masked_hint: Optional[str] = None  # e.g., "sk-...abc" for debugging


class SystemSettingsResponse(BaseModel):
    """Complete system settings response."""
    settings: List[SettingResponse]
    api_keys_status: List[ApiKeyStatus]


# ============ Default Settings ============

DEFAULT_SETTINGS = {
    "llm_provider": ("ollama", "Proveedor de IA: ollama (local, GPU)"),
    "ollama_model": ("gemma3:4b", "Modelo de extracción y matching (gemma3:4b recomendado)"),
    "embedding_model": ("nomic-embed-text", "Modelo de embeddings para búsqueda semántica"),
    "ollama_host": ("http://ollama:11434", "URL del servidor Ollama"),
    "upload_dir": ("./uploads", "Directorio para archivos CV subidos"),
    "pii_masking_enabled": ("false", "Enmascarar datos personales (innecesario con Ollama local)"),
    "data_retention_days": ("730", "Días para retener datos de candidatos"),
}


# ============ Helper Functions ============

def require_admin(user: UserResponse):
    """Verify user is admin, raise 403 if not."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden acceder a esta función"
        )


async def get_setting(db: AsyncSession, key: str) -> Optional[str]:
    """Get a single setting value from database."""
    result = await db.execute(
        select(SystemSettingDB).where(SystemSettingDB.key == key)
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


async def set_setting(db: AsyncSession, key: str, value: str, description: Optional[str] = None):
    """Set a setting value in database (upsert)."""
    result = await db.execute(
        select(SystemSettingDB).where(SystemSettingDB.key == key)
    )
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.value = value
        if description:
            setting.description = description
    else:
        setting = SystemSettingDB(
            key=key,
            value=value,
            description=description or DEFAULT_SETTINGS.get(key, ("", ""))[1]
        )
        db.add(setting)
    
    await db.commit()


def get_api_key_status() -> List[ApiKeyStatus]:
    """Check which API keys are configured in .env (without exposing them)."""
    statuses = []
    
    # Gemini
    gemini_key = settings.GEMINI_API_KEY
    statuses.append(ApiKeyStatus(
        provider="gemini",
        configured=bool(gemini_key),
        masked_hint=f"{gemini_key[:4]}...{gemini_key[-4:]}" if gemini_key and len(gemini_key) > 8 else None
    ))
    
    # OpenAI
    openai_key = settings.OPENAI_API_KEY
    statuses.append(ApiKeyStatus(
        provider="openai",
        configured=bool(openai_key),
        masked_hint=f"{openai_key[:4]}...{openai_key[-4:]}" if openai_key and len(openai_key) > 8 else None
    ))
    
    # Ollama (check host, not key)
    statuses.append(ApiKeyStatus(
        provider="ollama",
        configured=True,  # Ollama doesn't need API key
        masked_hint=settings.OLLAMA_HOST
    ))
    
    return statuses


# ============ Endpoints ============

@router.get("/settings", response_model=SystemSettingsResponse)
async def get_all_settings(
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all system settings.
    Admin only.
    """
    require_admin(current_user)
    
    # Get settings from database
    result = await db.execute(select(SystemSettingDB))
    db_settings = result.scalars().all()
    
    # Create response with DB values, filling in defaults for missing ones
    settings_dict = {s.key: s for s in db_settings}
    response_settings = []
    
    for key, (default_value, description) in DEFAULT_SETTINGS.items():
        if key in settings_dict:
            s = settings_dict[key]
            response_settings.append(SettingResponse(
                key=s.key,
                value=s.value,
                description=s.description or description,
                updated_at=s.updated_at
            ))
        else:
            response_settings.append(SettingResponse(
                key=key,
                value=default_value,
                description=description
            ))
    
    return SystemSettingsResponse(
        settings=response_settings,
        api_keys_status=get_api_key_status()
    )


@router.put("/settings")
async def update_settings(
    request: SettingsUpdateRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update system settings.
    Admin only. Only non-sensitive settings can be changed.
    API keys must be configured in .env file.
    """
    require_admin(current_user)
    
    # Validate only allowed keys
    allowed_keys = set(DEFAULT_SETTINGS.keys())
    for key in request.settings.keys():
        if key not in allowed_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Setting '{key}' no es configurable desde esta interfaz"
            )
    
    # Update each setting
    for key, value in request.settings.items():
        await set_setting(db, key, value)
    
    logger.info(f"Admin {current_user.email} updated settings: {list(request.settings.keys())}")
    
    return {"message": "Configuración actualizada correctamente", "updated": list(request.settings.keys())}


@router.get("/settings/status")
async def get_settings_status(
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    Get quick status of system configuration.
    Shows which API keys are configured without exposing them.
    """
    require_admin(current_user)
    
    return {
        "api_keys": get_api_key_status(),
        "current_provider": settings.LLM_PROVIDER,
        "environment": settings.ENVIRONMENT,
    }
