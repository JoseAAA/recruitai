"""
Registro de consumo del LLM (tokens + latencia) para KPIs, OKRs y costeo.
====================================================================

Cada operación de IA del sistema —extraer un CV, hacer matching, explicar al
candidato, analizar una vacante— llama al LLM una o varias veces. Este módulo
persiste, por cada llamada, los **tokens reales** que reportó la API del
proveedor y el **tiempo** que tardó, junto al contexto de negocio (candidato,
vacante, usuario). Con esos datos el panel ``/admin/usage`` responde:

- ¿Cuánto cuesta, en promedio, procesar un CV? ¿Y un análisis de matching?
- ¿Cuánto tarda cada etapa? (KPI de experiencia del reclutador)
- ¿Qué proveedor conviene por costo/latencia? (decisión de negocio)

Diseño espejo de :class:`app.core.privacy.AuditLogger`: el recorder recibe la
sesión DB por inyección y **nunca** rompe la operación principal — si el insert
falla, se loguea un warning y la request continúa. Medir no puede degradar el
servicio.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = logging.getLogger(__name__)


# ── Precios de referencia (USD por 1.000.000 de tokens) ────────────────────────
# Fuente: páginas de pricing oficiales de cada proveedor. SON ESTIMACIONES para
# el costeo del panel — los precios cambian; actualízalos aquí cuando el
# proveedor los ajuste. Ollama es local: costo de API = 0 (el costo real es la
# electricidad/GPU, fuera del alcance de este cálculo).
#
# Clave: nombre de modelo en minúsculas (match por prefijo). Valores en USD/1M.
LLM_PRICING_USD_PER_1M: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o-mini":        {"input": 0.15,  "output": 0.60},
    "gpt-4o":             {"input": 2.50,  "output": 10.00},
    "gpt-4.1-mini":       {"input": 0.40,  "output": 1.60},
    "gpt-4.1":            {"input": 2.00,  "output": 8.00},
    # Google Gemini (free tier = 0, pero el tier pagado cuesta esto)
    "gemini-2.5-flash":   {"input": 0.30,  "output": 2.50},
    "gemini-1.5-flash":   {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash":   {"input": 0.10,  "output": 0.40},
    # Groq
    "llama-3.3-70b":      {"input": 0.59,  "output": 0.79},
    "llama-3.1-8b":       {"input": 0.05,  "output": 0.08},
}


def estimate_cost_usd(
    provider: Optional[str],
    model: Optional[str],
    input_tokens: Optional[int],
    output_tokens: Optional[int],
) -> float:
    """Estima el costo en USD de una llamada según el precio del modelo.

    Ollama (local) siempre devuelve 0. Si el modelo no está en la tabla de
    precios, devuelve 0 (mejor subestimar que inventar un costo falso) y deja
    al panel mostrar los tokens crudos. Hace match por prefijo para tolerar
    sufijos de versión (``gpt-4o-mini-2024-07-18`` → ``gpt-4o-mini``).
    """
    if (provider or "").lower() == "ollama":
        return 0.0
    if not model:
        return 0.0
    model_lower = model.lower()
    price = None
    for prefix, p in LLM_PRICING_USD_PER_1M.items():
        if model_lower.startswith(prefix):
            price = p
            break
    if price is None:
        return 0.0
    cost = (input_tokens or 0) / 1_000_000 * price["input"]
    cost += (output_tokens or 0) / 1_000_000 * price["output"]
    return round(cost, 6)


class LLMUsageRecorder:
    """Persiste filas de consumo del LLM en la tabla ``llm_usage``.

    No es singleton: necesita la sesión DB de la request para escribir en la
    misma conexión que el resto de la operación. Igual que ``AuditLogger``.
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self._db = db_session

    async def record(
        self,
        *,
        operation: str,
        usage: Optional[dict[str, Any]] = None,
        candidate_id: Optional[Any] = None,
        job_id: Optional[Any] = None,
        user_id: Optional[str] = None,
        batch_id: Optional[Any] = None,
        preprocess_ms: Optional[int] = None,
        success: Optional[bool] = None,
        error_type: Optional[str] = None,
        commit: bool = True,
    ) -> None:
        """Registra una llamada al LLM.

        Args:
            operation: ``extract_cv`` | ``match`` | ``explain`` | ``extract_job``.
            usage: dict que llena el motor LLM (``usage_out``) con las claves
                ``provider``, ``model``, ``input_tokens``, ``output_tokens``,
                ``latency_ms`` y ``success``. Puede venir vacío si la llamada
                falló antes de obtener tokens.
            candidate_id / job_id / user_id / batch_id: contexto de negocio.
            preprocess_ms: tiempo de lectura del documento (solo ``extract_cv``).
            success / error_type: overridean lo que venga en ``usage`` (útil
                para registrar fallos como cuota agotada).
            commit: si es False, solo hace ``add`` (para inserciones en lote;
                el llamador hace un único commit después).
        """
        if self._db is None:
            return

        usage = usage or {}
        in_tok = usage.get("input_tokens")
        out_tok = usage.get("output_tokens")
        total = None
        if in_tok is not None or out_tok is not None:
            total = (in_tok or 0) + (out_tok or 0)

        ok = success if success is not None else bool(usage.get("success", True))

        try:
            from app.db.models import LLMUsageDB

            row = LLMUsageDB(
                operation=operation,
                provider=str(usage.get("provider") or "")[:20],
                model=(usage.get("model") or None),
                input_tokens=in_tok,
                output_tokens=out_tok,
                total_tokens=total,
                latency_ms=usage.get("latency_ms"),
                preprocess_ms=preprocess_ms,
                candidate_id=_as_uuid(candidate_id),
                job_id=_as_uuid(job_id),
                user_id=str(user_id) if user_id is not None else None,
                batch_id=_as_uuid(batch_id),
                success=ok,
                error_type=error_type,
            )
            self._db.add(row)
            if commit:
                await self._db.commit()
        except Exception as e:  # nunca romper la operación principal
            logger.warning(f"Failed to persist llm_usage row ({operation}): {e}")
            if commit:
                try:
                    await self._db.rollback()
                except Exception:
                    pass


def _as_uuid(value: Any) -> Optional[UUID]:
    """Convierte a UUID de forma tolerante (acepta str, UUID o None)."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def get_usage_recorder(db: AsyncSession = Depends(get_db)) -> LLMUsageRecorder:
    """FastAPI dependency: ``LLMUsageRecorder`` con la sesión DB de la request."""
    return LLMUsageRecorder(db_session=db)
