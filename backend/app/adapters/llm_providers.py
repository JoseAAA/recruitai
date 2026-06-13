"""
LLM Providers - Multi-provider abstraction for LLM integrations.
Supports: Ollama (local), OpenAI, Google Gemini
"""
import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Type, TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMRateLimitError(Exception):
    """El proveedor LLM agotó su cuota (HTTP 429) y los reintentos no bastaron.

    Se propaga hasta las rutas HTTP para responder 503 con mensaje claro,
    en lugar de degradar en silencio al extractor regex (que guarda datos
    corruptos como si fueran buenos — visto con Groq free tier: 12k tokens/min
    se agotan subiendo ~3 CVs seguidos).
    """


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Atributo ``last_usage``: tras cada ``generate()`` exitoso, el proveedor
    deja aquí los tokens reales reportados por su API:
    ``{"input_tokens": int, "output_tokens": int}`` (o ``None`` si la API no
    los devolvió). Las rutas lo leen para registrar consumo en ``llm_usage``
    (auditoría de costos por candidato/vacante).
    """

    last_usage: Optional[dict] = None
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        json_mode: bool = False,
        json_schema: Optional[dict] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        system_prompt: str = None,
    ) -> str:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available."""
        pass
    
    async def close(self):
        """Close any open connections. Override in subclasses."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider — Edge AI, 100% privado."""
    
    def __init__(self, client: Optional[httpx.AsyncClient] = None, model: Optional[str] = None):
        self.base_url = settings.OLLAMA_HOST
        self.model = model or settings.MATCH_MODEL
        self._client = client
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            # CV extraction with gemma4:e2b on GPU produces 4-7k tokens of JSON
            # which can take 90-180s. The original 120s ceiling timed out
            # mid-generation and the response was discarded — silent fallback
            # to the regex extractor with bad results.
            # Granular config: short connect, generous read for streaming
            # responses, no overall write/pool cap.
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10.0, read=600.0, write=60.0, pool=10.0),
            )
        return self._client

    async def close(self):
        """Close HTTP client to free connections."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    @property
    def name(self) -> str:
        return f"Ollama ({self.model})"
    
    async def is_available(self) -> bool:
        """Check if Ollama is running AND has the configured model installed."""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                model_names = [m.get("name", "") for m in models]

                for name in model_names:
                    if self.model in name:
                        return True

                logger.warning(
                    f"Ollama running but model '{self.model}' not found. "
                    f"Available: {model_names}."
                )
                return False
            return False
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False

    async def ensure_model(self) -> bool:
        """Pull model from Ollama registry if not already installed.

        Called once at startup — not on every request. Changing MATCH_MODEL
        or EXTRACTION_MODEL in .env is enough: the new model is pulled
        automatically on the next container start.
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                models = response.json().get("models", [])
                if any(self.model in m.get("name", "") for m in models):
                    logger.info(f"Model '{self.model}' already installed — skipping pull")
                    return True

            logger.info(f"Model '{self.model}' not found — pulling from Ollama registry (this may take a few minutes)...")
            pull_response = await self.client.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model, "stream": False},
                timeout=600.0,  # 10 min — gemma3:4b is ~2.5GB
            )
            if pull_response.status_code == 200:
                logger.info(f"Model '{self.model}' pulled successfully")
                return True
            else:
                logger.error(f"Failed to pull '{self.model}': HTTP {pull_response.status_code} — {pull_response.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"ensure_model failed for '{self.model}': {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        json_mode: bool = False,
        json_schema: Optional[dict] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        system_prompt: str = None,
    ) -> str:
        """
        Generate text using Ollama /api/chat endpoint.

        Uses /api/chat instead of /api/generate because:
        - Supports system role → better instruction following
        - Standard message format compatible with all models
        - Supports constrained decoding via JSON Schema (json_schema param)

        json_schema: when provided, Ollama uses constrained decoding — the model
        physically cannot emit tokens that violate the schema. More reliable than
        free-form json_mode=True. Requires Ollama >= 0.5.
        Ref: Ollama structured outputs docs (2024), Willard & Louf "Efficient Guided
        Generation for Large Language Models" (2023).
        """
        messages = []
        
        # System prompt — gives the model its role/instructions
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # User message — the actual prompt
        messages.append({"role": "user", "content": prompt})
        
        request_body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": settings.OLLAMA_NUM_CTX,
            }
        }

        # Aviso si la entrada (system + user) excede num_ctx — Ollama trunca en
        # silencio desde el inicio del prompt y el modelo pierde los datos de
        # contacto que están en la cabecera del CV. Estimación grosera ~4 chars/token.
        total_input_chars = sum(len(m["content"]) for m in messages)
        estimated_input_tokens = total_input_chars // 4
        if estimated_input_tokens > settings.OLLAMA_NUM_CTX:
            logger.warning(
                f"Input ~{estimated_input_tokens} tokens excede num_ctx={settings.OLLAMA_NUM_CTX}. "
                f"Ollama truncará desde el inicio del prompt — la cabecera del CV puede perderse. "
                f"Sube OLLAMA_NUM_CTX en .env o reduce MAX_CV_LENGTH."
            )
        else:
            logger.debug(
                f"Ollama request: ~{estimated_input_tokens} tokens in, num_ctx={settings.OLLAMA_NUM_CTX}, "
                f"num_predict={max_tokens}"
            )

        # OLLAMA_THINKING=false → desactiva el chain-of-thought en modelos thinking
        # (qwen3, deepseek-r1). En modelos normales (gemma3:4b) este parámetro
        # es ignorado por Ollama, por lo que es seguro enviarlo siempre.
        if not settings.OLLAMA_THINKING:
            request_body["think"] = False
        if json_schema:
            # Constrained decoding: model cannot emit tokens that violate the schema.
            # json_schema takes priority over json_mode when both are provided.
            request_body["format"] = json_schema
        elif json_mode:
            request_body["format"] = "json"
        
        self.last_usage = None
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json=request_body
        )
        response.raise_for_status()
        data = response.json()
        if "prompt_eval_count" in data or "eval_count" in data:
            self.last_usage = {
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            }

        # /api/chat returns {"message": {"role": "assistant", "content": "...", "thinking": "..."}}
        # qwen3.5 uses a separate "thinking" field for chain-of-thought reasoning.
        # When thinking is enabled and the final answer is also JSON, both fields are populated.
        # We prefer "content" (the actual answer), but fall back to "thinking" only as a last resort.
        message = data.get("message", {})
        content = message.get("content", "")
        thinking = message.get("thinking", "")

        # If content is empty but thinking has data, the model put its response in thinking.
        # This happens when json_mode+thinking fills tokens before generating a separate content.
        # In that case extract any JSON from the thinking block.
        if not content.strip() and thinking.strip():
            logger.debug(f"Ollama: content empty, using thinking field ({len(thinking)} chars)")
            return thinking

        return content


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (GPT-4o-mini, GPT-4o, etc.).

    Sirve también como **base genérica** para cualquier proveedor compatible
    con el SDK de OpenAI (Groq, Together, Fireworks, OpenRouter, etc.). Las
    subclases solo necesitan sobreescribir ``_provider_label``, ``api_key``,
    ``model`` y ``base_url`` en su ``__init__``.
    """

    # Etiqueta del proveedor para logging y ``name``. Subclases lo cambian.
    _provider_label: str = "OpenAI"

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.base_url = "https://api.openai.com/v1"
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=120.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._client

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def name(self) -> str:
        return f"{self._provider_label} ({self.model})"

    async def is_available(self) -> bool:
        if not self.api_key:
            logger.warning(f"{self._provider_label} API key not configured")
            return False
        try:
            # Simple check - list models endpoint (OpenAI-compatible en todos
            # los proveedores que extienden esta clase).
            response = await self.client.get(f"{self.base_url}/models", timeout=10.0)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"{self._provider_label} not available: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        json_mode: bool = False,
        json_schema: Optional[dict] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        system_prompt: str = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request_body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if json_mode:
            request_body["response_format"] = {"type": "json_object"}

        # Reintento ante 429 (cuota: Groq free = 12k tokens/min, Retry-After
        # indica la espera exacta) y ante 5xx transitorios ("model overloaded").
        # Sin esto, el error burbujeaba como excepción genérica y el llamador
        # degradaba a extracción regex con datos corruptos.
        RETRYABLE = {429, 500, 502, 503, 504}
        max_attempts = 3
        self.last_usage = None
        for attempt in range(max_attempts):
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=request_body,
            )
            if response.status_code in RETRYABLE and attempt < max_attempts - 1:
                retry_after = response.headers.get("retry-after")
                try:
                    wait_time = min(float(retry_after), 65.0) if retry_after else 2.0 ** (attempt + 1)
                except ValueError:
                    wait_time = 2.0 ** (attempt + 1)
                logger.warning(
                    f"{self._provider_label} HTTP {response.status_code} — "
                    f"reintento {attempt + 1}/{max_attempts - 1} en {wait_time:.0f}s"
                )
                await asyncio.sleep(wait_time)
                continue
            if response.status_code in RETRYABLE:
                raise LLMRateLimitError(
                    f"{self._provider_label}: servicio saturado o cuota agotada "
                    f"tras {max_attempts} intentos."
                )
            response.raise_for_status()
            data = response.json()
            usage = data.get("usage") or {}
            if usage:
                self.last_usage = {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                }
            return data["choices"][0]["message"]["content"]


class GroqProvider(OpenAIProvider):
    """Groq Cloud provider — drop-in del SDK OpenAI, solo cambia ``base_url``.

    Ventajas operativas (mayo 2026):
      - **Velocidad**: 5-10x más rápido que OpenAI/Gemini en latencia, ~840
        tok/s con Llama 3.3 70B en GPUs LPU custom.
      - **Política de datos**: NO entrenan con tus datos. Retención 30 días
        para debugging; opción Zero Data Retention disponible vía DPA.
      - **Compatibilidad**: el wire protocol es 100% OpenAI — heredamos
        ``generate`` e ``is_available`` sin modificar.

    Aplica el mismo PII masking que OpenAI/Gemini cuando se activa cloud, ver
    ``core.config.Settings.validate_llm_provider_and_pii``.
    """

    _provider_label = "Groq"

    def __init__(self):
        # Saltamos super().__init__() porque sobreescribimos los 3 atributos
        # con los valores específicos de Groq.
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.GROQ_MODEL
        self.base_url = "https://api.groq.com/openai/v1"
        self._client: Optional[httpx.AsyncClient] = None


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    # Marcapasos compartido entre TODAS las instancias: el free tier de
    # Gemini limita por MINUTO (~10-15 req/min). Disparar el matching con
    # concurrencia 2 sin pausa provocaba una tormenta de 429 + reintentos
    # que convertía 10 candidatos en 12 minutos (y nginx corta a los 60s).
    # Espaciando los inicios de petición nunca se excede el ritmo: 10
    # candidatos ≈ 1 min y todas las llamadas pasan a la primera.
    # GEMINI_MIN_REQUEST_INTERVAL=0 en .env lo desactiva (tier pagado).
    _pace_lock: "asyncio.Lock" = asyncio.Lock()
    _last_request_at: float = 0.0

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self._client: Optional[httpx.AsyncClient] = None
        self.min_interval = float(
            getattr(settings, "GEMINI_MIN_REQUEST_INTERVAL", 6.0)
        )

    async def _pace(self) -> None:
        """Garantiza ``min_interval`` segundos entre inicios de petición."""
        if self.min_interval <= 0:
            return
        import time
        async with GeminiProvider._pace_lock:
            now = time.monotonic()
            wait = GeminiProvider._last_request_at + self.min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            GeminiProvider._last_request_at = time.monotonic()
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client
    
    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    @property
    def name(self) -> str:
        return f"Gemini ({self.model})"
    
    async def is_available(self) -> bool:
        if not self.api_key:
            logger.warning("Gemini API key not configured")
            return False
        try:
            # Check by listing models. La key va por HEADER, no por query
            # string: las URLs aparecen en logs de error/proxies y filtraban
            # la API key completa (visto en docker logs el 2026-06-12).
            response = await self.client.get(
                f"{self.base_url}/models",
                headers={"x-goog-api-key": self.api_key},
                timeout=10.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Gemini not available: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        json_mode: bool = False,
        json_schema: Optional[dict] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        max_retries: int = 3,
        system_prompt: str = None,
    ) -> str:
        """
        Generate text with automatic retry on rate limit (429) errors.
        Uses exponential backoff: 1s, 2s, 4s delays between retries.
        json_schema is accepted for API compatibility but Gemini uses its own
        structured output mechanism (responseMimeType + responseSchema).
        """
        import asyncio

        # Gemini uses different endpoint structure. La key va por header
        # x-goog-api-key (no query string): los errores HTTP incluyen la URL
        # completa en logs y eso filtraba la API key.
        url = f"{self.base_url}/models/{self.model}:generateContent"
        
        # Gemini REST API: system instructions go as a separate field
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        
        request_body = {
            "contents": [
                {"parts": [{"text": full_prompt}]}
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        if json_mode:
            request_body["generationConfig"]["responseMimeType"] = "application/json"

        # Gemini 2.5+ Flash es un modelo "pensante": consume maxOutputTokens
        # en razonamiento interno y truncaba el JSON del matching (el parser
        # rescataba un dict parcial → scores default 50/50/50 silenciosos).
        # Para extracción/matching estructurado el thinking no aporta:
        # presupuesto 0 = toda la salida disponible para el JSON, menos
        # latencia y menos costo. Solo variantes flash lo aceptan (Pro no).
        if "flash" in (self.model or "").lower():
            request_body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
        
        def _wait_time(resp: Optional[httpx.Response], attempt: int) -> float:
            """Espera honrando Retry-After si Gemini lo envía; si no,
            backoff 5/15/30s — la cuota free es por MINUTO, así que 1-4s
            (el backoff anterior) casi nunca alcanzaba a recuperarla."""
            if resp is not None:
                retry_after = resp.headers.get("retry-after")
                if retry_after:
                    try:
                        return min(float(retry_after), 65.0)
                    except ValueError:
                        pass
            return float(5 * (3 ** attempt))  # 5, 15, 45

        # 429 = cuota; 5xx = "model overloaded" transitorio (visto 503 en
        # free tier 2026-06-12). Ambos se reintentan; agotados los intentos
        # se lanza el error TIPADO para que extracción/matching fallen claro
        # en lugar de degradar al fallback regex silencioso.
        RETRYABLE = {429, 500, 502, 503, 504}

        last_error = None
        self.last_usage = None
        for attempt in range(max_retries):
            try:
                await self._pace()
                response = await self.client.post(
                    url, json=request_body, headers={"x-goog-api-key": self.api_key}
                )

                if response.status_code in RETRYABLE:
                    wait = _wait_time(response, attempt)
                    logger.warning(
                        f"Gemini {response.status_code}, retry "
                        f"{attempt + 1}/{max_retries} in {wait:.0f}s"
                    )
                    last_error = f"HTTP {response.status_code}"
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                data = response.json()

                # Tokens reales reportados por la API (mismo contrato que
                # Ollama/OpenAI: input_tokens/output_tokens). Gemini cuenta el
                # "thinking" dentro de candidatesTokenCount, por eso registramos
                # también el total para el costeo en llm_usage.
                meta = data.get("usageMetadata") or {}
                if meta:
                    self.last_usage = {
                        "input_tokens": meta.get("promptTokenCount", 0),
                        "output_tokens": meta.get("candidatesTokenCount", 0),
                    }

                # Extract text from Gemini response structure
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError) as e:
                    logger.error(f"Failed to parse Gemini response: {e}")
                    return ""

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in RETRYABLE:
                    wait = _wait_time(e.response, attempt)
                    logger.warning(f"Gemini {e.response.status_code}, waiting {wait:.0f}s...")
                    await asyncio.sleep(wait)
                    continue
                raise
            except Exception as e:
                last_error = e
                logger.error(f"Gemini generate error: {e}")
                raise

        logger.error(f"Gemini max retries exceeded. Last error: {last_error}")
        raise LLMRateLimitError(
            f"Gemini: servicio saturado o cuota agotada tras {max_retries} intentos."
        )


def get_llm_provider() -> LLMProvider:
    """Factory: devuelve el proveedor LLM configurado en ``LLM_PROVIDER``.

    **Fail-fast por diseño.** Antes existía un fallback silencioso a Ollama
    cuando el provider cloud no tenía API key; eso causaba bugs sutiles donde
    el ingeniero creía estar usando Groq/Gemini y en realidad seguía en local
    sin enterarse. Hoy:

      - Si ``LLM_PROVIDER`` es cloud y falta la API key correspondiente, se
        levanta ``ValueError`` con un mensaje claro. La validación principal
        ocurre antes en ``core.config.validate_llm_provider_and_pii``, pero
        repetimos el check aquí como defensa en profundidad.
      - Si ``LLM_PROVIDER`` no es válido, también levanta error.
      - No hay "modo silencioso que parece funcionar".
    """
    provider_name = (settings.LLM_PROVIDER or "ollama").lower()

    if provider_name == "ollama":
        logger.info("Using Ollama provider (local, datos nunca salen)")
        return OllamaProvider()

    if provider_name == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "LLM_PROVIDER=openai pero OPENAI_API_KEY no está en .env. "
                "Configúrala o cambia a LLM_PROVIDER=ollama."
            )
        logger.info(f"Using OpenAI provider (model={settings.OPENAI_MODEL})")
        return OpenAIProvider()

    if provider_name == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "LLM_PROVIDER=gemini pero GEMINI_API_KEY no está en .env. "
                "Configúrala o cambia a LLM_PROVIDER=ollama."
            )
        logger.info(f"Using Gemini provider (model={settings.GEMINI_MODEL})")
        return GeminiProvider()

    if provider_name == "groq":
        if not settings.GROQ_API_KEY:
            raise ValueError(
                "LLM_PROVIDER=groq pero GROQ_API_KEY no está en .env. "
                "Obtén una gratis en https://console.groq.com o cambia a "
                "LLM_PROVIDER=ollama."
            )
        logger.info(f"Using Groq provider (model={settings.GROQ_MODEL})")
        return GroqProvider()

    raise ValueError(
        f"LLM_PROVIDER='{provider_name}' no es válido. "
        f"Opciones: ollama, openai, gemini, groq."
    )


# Singleton provider instance
_provider: Optional[LLMProvider] = None


def get_provider() -> LLMProvider:
    """Get cached provider instance."""
    global _provider
    if _provider is None:
        _provider = get_llm_provider()
    return _provider


async def reset_provider():
    """Reset provider (useful for testing or config changes)."""
    global _provider
    _provider = None
