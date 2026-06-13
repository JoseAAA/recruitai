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
    # True si este campo viene del archivo .env (read-only desde la UI).
    # False si es configurable y vive en BD (editable desde la UI).
    source_env: bool = False


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
    "llm_provider": ("ollama", "Proveedor de IA: ollama | groq | gemini | openai"),
    "ollama_model": ("gemma3:4b", "Modelo Ollama para extracción y matching (gemma3:4b recomendado)"),
    "groq_model": ("llama-3.3-70b-versatile", "Modelo Groq (drop-in OpenAI SDK, ultra rápido)"),
    "gemini_model": ("gemini-2.5-flash", "Modelo Gemini (free tier ~1.5k req/día)"),
    "openai_model": ("gpt-4o-mini", "Modelo OpenAI"),
    "ollama_host": ("http://ollama:11434", "URL del servidor Ollama (solo si LLM_PROVIDER=ollama)"),
    "embeddings_host": ("http://embeddings:8080", "URL del servicio de embeddings TEI (siempre activo)"),
    "embedding_model": (
        "Snowflake/snowflake-arctic-embed-m-v2.0",
        "Modelo de embeddings multilingüe (servido por TEI, independiente del LLM)",
    ),
    "upload_dir": ("./uploads", "Directorio para archivos CV subidos"),
    "pii_masking_enabled": (
        "auto",
        "Enmascarar PII antes de enviar al LLM. 'auto' = ON con cloud, OFF con Ollama local",
    ),
    "data_retention_days": ("730", "Días para retener datos de candidatos (LPDP Perú)"),
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


def _mask_key(key: Optional[str]) -> Optional[str]:
    """Devuelve un hint enmascarado tipo 'gsk_...xyz' o None si la key es corta/vacía."""
    if not key or len(key) <= 8:
        return None
    return f"{key[:4]}...{key[-4:]}"


def get_api_key_status() -> List[ApiKeyStatus]:
    """Check which API keys are configured in .env (without exposing them)."""
    statuses = []

    # Groq (drop-in OpenAI SDK, ultra rápido)
    statuses.append(ApiKeyStatus(
        provider="groq",
        configured=bool(settings.GROQ_API_KEY),
        masked_hint=_mask_key(settings.GROQ_API_KEY),
    ))

    # Gemini
    statuses.append(ApiKeyStatus(
        provider="gemini",
        configured=bool(settings.GEMINI_API_KEY),
        masked_hint=_mask_key(settings.GEMINI_API_KEY),
    ))

    # OpenAI
    statuses.append(ApiKeyStatus(
        provider="openai",
        configured=bool(settings.OPENAI_API_KEY),
        masked_hint=_mask_key(settings.OPENAI_API_KEY),
    ))

    # Ollama (servicio local, no API key)
    statuses.append(ApiKeyStatus(
        provider="ollama",
        configured=True,
        masked_hint=settings.OLLAMA_HOST,
    ))

    # Embeddings (servicio TEI local, independiente del LLM)
    statuses.append(ApiKeyStatus(
        provider="embeddings",
        configured=True,
        masked_hint=getattr(settings, "EMBEDDINGS_HOST", "http://embeddings:8080"),
    ))

    return statuses


# ============ Endpoints ============

# Mapa de keys → propiedad de ``settings`` cargada desde .env.
# Estas SIEMPRE se devuelven con su valor runtime real, ignorando lo que haya
# en la tabla system_settings (que se quedaba desactualizada y mentía al admin
# en la UI). Para cambiarlas hay que editar .env y reiniciar el backend.
ENV_BACKED_KEYS: Dict[str, str] = {
    "llm_provider":         "LLM_PROVIDER",
    "ollama_model":         "OLLAMA_MODEL",
    "groq_model":           "GROQ_MODEL",
    "gemini_model":         "GEMINI_MODEL",
    "openai_model":         "OPENAI_MODEL",
    "ollama_host":          "OLLAMA_HOST",
    "embeddings_host":      "EMBEDDINGS_HOST",
    "embedding_model":      "EMBEDDING_MODEL",
    "pii_masking_enabled":  "PII_MASKING_ENABLED",
    "data_retention_days":  "DATA_RETENTION_DAYS",
    "upload_dir":           "UPLOAD_DIR",
}


@router.get("/settings", response_model=SystemSettingsResponse)
async def get_all_settings(
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Devuelve la configuración del sistema **tal como está corriendo ahora**.

    Antes el endpoint leía de la tabla ``system_settings`` (BD) con fallback a
    defaults. Eso causaba que la UI mintiera al admin: si alguien cambiaba
    ``LLM_PROVIDER`` en ``.env`` y reiniciaba el backend, la UI seguía
    mostrando el valor viejo de BD durante meses.

    Solución: cada campo ligado a ``.env`` se devuelve con su valor runtime
    real desde ``settings.X`` y se marca ``source_env=True`` para que la UI
    lo pinte como read-only con un badge ".env".
    """
    require_admin(current_user)

    # Mapa de overrides en BD para campos NO ligados a .env (configurables).
    result = await db.execute(select(SystemSettingDB))
    db_settings = {s.key: s for s in result.scalars().all()}

    response_settings: List[SettingResponse] = []

    for key, (default_value, description) in DEFAULT_SETTINGS.items():
        if key in ENV_BACKED_KEYS:
            # Siempre runtime, nunca BD. El admin debe editar .env para cambiar.
            runtime_value = getattr(settings, ENV_BACKED_KEYS[key], None)
            value_str = "" if runtime_value is None else str(runtime_value)
            response_settings.append(SettingResponse(
                key=key,
                value=value_str,
                description=description,
                source_env=True,
            ))
        elif key in db_settings:
            s = db_settings[key]
            response_settings.append(SettingResponse(
                key=key,
                value=s.value,
                description=s.description or description,
                updated_at=s.updated_at,
                source_env=False,
            ))
        else:
            response_settings.append(SettingResponse(
                key=key,
                value=default_value,
                description=description,
                source_env=False,
            ))

    return SystemSettingsResponse(
        settings=response_settings,
        api_keys_status=get_api_key_status(),
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
    
    # Validar que la key sea conocida
    allowed_keys = set(DEFAULT_SETTINGS.keys())
    for key in request.settings.keys():
        if key not in allowed_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Setting '{key}' no es configurable desde esta interfaz"
            )
        # Las keys ligadas a .env no pueden cambiarse desde la UI — solo
        # editando el archivo .env y reiniciando el backend. Esto evita
        # divergencia entre lo que el sistema usa (runtime) y lo que el admin
        # cree haber cambiado (BD).
        if key in ENV_BACKED_KEYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"'{key}' está configurado en el archivo .env y no se "
                    f"puede cambiar desde la UI. Edita .env y reinicia el "
                    f"backend con: docker restart recruitai-backend"
                ),
            )

    # Persistir cada setting NO-env en la BD
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
