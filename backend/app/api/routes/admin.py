"""
Admin API Routes - System Settings Management
Only accessible by users with admin role.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.db.models import SystemSettingDB, LLMUsageDB
from app.api.routes.auth import get_current_active_user, UserResponse
from app.core.config import settings
from app.core.usage import estimate_cost_usd, LLM_PRICING_USD_PER_1M

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


# ============ Consumo del LLM (tokens, tiempo, costo) — base de KPIs/OKRs ======

# Etiquetas legibles por operación (para el panel del ingeniero/admin).
_OPERATION_LABELS = {
    "extract_cv": "Extracción de CV",
    "match": "Análisis de matching",
    "explain": "Explicación al candidato",
    "extract_job": "Análisis de vacante",
}


@router.get("/usage")
async def get_llm_usage(
    days: int = Query(30, ge=1, le=365, description="Ventana de análisis en días"),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Resumen de consumo del LLM para construir KPIs/OKRs y costear el sistema.

    Agrega la tabla ``llm_usage`` por operación y por proveedor/modelo dentro de
    una ventana temporal (por defecto 30 días) y devuelve:

    - ``totales``: llamadas, tokens (entrada/salida/total), costo estimado USD,
      tasa de éxito.
    - ``por_operacion``: mismos números desglosados por etapa (extracción,
      matching, explicación, análisis de vacante) + tiempos promedio. Aquí salen
      los KPIs clave: **costo y tiempo promedio por CV** y **por análisis**.
    - ``por_proveedor``: comparativa entre Ollama/OpenAI/Gemini/Groq.
    - ``serie_diaria``: tokens y costo por día (para gráficas de tendencia).

    Solo admin. Esta vista es técnica (tokens, costos) — por diseño no se muestra
    en la UI de RRHH (AGENTS §7); vive en el panel del ingeniero.
    """
    require_admin(current_user)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    failures = func.sum(case((LLMUsageDB.success.is_(False), 1), else_=0))
    grouped = await db.execute(
        select(
            LLMUsageDB.operation,
            LLMUsageDB.provider,
            LLMUsageDB.model,
            func.count().label("calls"),
            func.coalesce(func.sum(LLMUsageDB.input_tokens), 0).label("in_tok"),
            func.coalesce(func.sum(LLMUsageDB.output_tokens), 0).label("out_tok"),
            func.coalesce(func.sum(LLMUsageDB.latency_ms), 0).label("sum_latency"),
            func.coalesce(func.sum(LLMUsageDB.preprocess_ms), 0).label("sum_preprocess"),
            failures.label("failures"),
        )
        .where(LLMUsageDB.created_at >= since)
        .group_by(LLMUsageDB.operation, LLMUsageDB.provider, LLMUsageDB.model)
    )

    def _blank() -> dict:
        return {
            "calls": 0, "input_tokens": 0, "output_tokens": 0,
            "cost_usd": 0.0, "sum_latency_ms": 0, "sum_preprocess_ms": 0,
            "failures": 0,
        }

    totals = _blank()
    by_operation: dict[str, dict] = {}
    by_provider: dict[str, dict] = {}

    for r in grouped.all():
        cost = estimate_cost_usd(r.provider, r.model, r.in_tok, r.out_tok)
        for bucket in (
            totals,
            by_operation.setdefault(r.operation, _blank()),
            by_provider.setdefault(f"{r.provider}:{r.model or '-'}", _blank()),
        ):
            bucket["calls"] += r.calls
            bucket["input_tokens"] += int(r.in_tok)
            bucket["output_tokens"] += int(r.out_tok)
            bucket["cost_usd"] += cost
            bucket["sum_latency_ms"] += int(r.sum_latency)
            bucket["sum_preprocess_ms"] += int(r.sum_preprocess)
            bucket["failures"] += int(r.failures)

    def _finalize(b: dict, include_preprocess: bool = False) -> dict:
        calls = b["calls"] or 1
        out = {
            "llamadas": b["calls"],
            "tokens_entrada": b["input_tokens"],
            "tokens_salida": b["output_tokens"],
            "tokens_total": b["input_tokens"] + b["output_tokens"],
            "costo_usd": round(b["cost_usd"], 4),
            "costo_promedio_usd": round(b["cost_usd"] / calls, 6),
            "latencia_promedio_ms": round(b["sum_latency_ms"] / calls),
            "tasa_exito": round(1 - b["failures"] / calls, 4),
        }
        if include_preprocess:
            out["tiempo_lectura_promedio_ms"] = round(b["sum_preprocess_ms"] / calls)
            out["tiempo_total_promedio_ms"] = round(
                (b["sum_latency_ms"] + b["sum_preprocess_ms"]) / calls
            )
        return out

    # Serie diaria (tokens + costo por día), correcta por modelo.
    day_col = func.date_trunc("day", LLMUsageDB.created_at)
    daily_rows = await db.execute(
        select(
            day_col.label("day"),
            LLMUsageDB.provider,
            LLMUsageDB.model,
            func.count().label("calls"),
            func.coalesce(func.sum(LLMUsageDB.input_tokens), 0).label("in_tok"),
            func.coalesce(func.sum(LLMUsageDB.output_tokens), 0).label("out_tok"),
        )
        .where(LLMUsageDB.created_at >= since)
        .group_by(day_col, LLMUsageDB.provider, LLMUsageDB.model)
        .order_by(day_col)
    )
    serie: dict[str, dict] = {}
    for r in daily_rows.all():
        key = r.day.date().isoformat() if hasattr(r.day, "date") else str(r.day)[:10]
        d = serie.setdefault(key, {"fecha": key, "llamadas": 0, "tokens_total": 0, "costo_usd": 0.0})
        d["llamadas"] += r.calls
        d["tokens_total"] += int(r.in_tok) + int(r.out_tok)
        d["costo_usd"] = round(d["costo_usd"] + estimate_cost_usd(r.provider, r.model, r.in_tok, r.out_tok), 6)

    return {
        "ventana_dias": days,
        "proveedor_actual": (settings.LLM_PROVIDER or "").lower(),
        "totales": _finalize(totals),
        "por_operacion": {
            op: {"etiqueta": _OPERATION_LABELS.get(op, op), **_finalize(b, include_preprocess=(op == "extract_cv"))}
            for op, b in sorted(by_operation.items())
        },
        "por_proveedor": {k: _finalize(b) for k, b in sorted(by_provider.items())},
        "serie_diaria": [serie[k] for k in sorted(serie.keys())],
        "nota_costos": (
            "Los costos son estimaciones según precios públicos por modelo "
            "(editables en backend/app/core/usage.py). Ollama local = 0."
        ),
    }


@router.get("/usage/recent")
async def get_llm_usage_recent(
    limit: int = Query(50, ge=1, le=500),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Últimas llamadas al LLM (filas crudas) para auditar/depurar consumo.

    Útil para verificar que los tokens y tiempos se están registrando bien y
    para rastrear una operación puntual. Solo admin.
    """
    require_admin(current_user)
    rows = await db.execute(
        select(LLMUsageDB).order_by(LLMUsageDB.created_at.desc()).limit(limit)
    )
    out = []
    for r in rows.scalars().all():
        out.append({
            "id": str(r.id),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "operacion": r.operation,
            "etiqueta": _OPERATION_LABELS.get(r.operation, r.operation),
            "proveedor": r.provider,
            "modelo": r.model,
            "tokens_entrada": r.input_tokens,
            "tokens_salida": r.output_tokens,
            "tokens_total": r.total_tokens,
            "latencia_ms": r.latency_ms,
            "tiempo_lectura_ms": r.preprocess_ms,
            "costo_usd": estimate_cost_usd(r.provider, r.model, r.input_tokens, r.output_tokens),
            "candidate_id": str(r.candidate_id) if r.candidate_id else None,
            "job_id": str(r.job_id) if r.job_id else None,
            "batch_id": str(r.batch_id) if r.batch_id else None,
            "exito": r.success,
            "error": r.error_type,
        })
    return {"items": out, "total": len(out)}
