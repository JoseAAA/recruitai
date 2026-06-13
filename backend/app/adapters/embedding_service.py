"""
Embedding Service Adapter — text-embeddings-inference (TEI)
============================================================

Genera embeddings semánticos vía un servidor TEI (Hugging Face) **separado**
del LLM. Este es el patrón "separation of inference services" recomendado por
Chip Huyen, Eugene Yan y la arquitectura de referencia de Qdrant.

¿Por qué separado de Ollama?
- Embeddings y generación tienen perfiles de carga opuestos (frecuentes y
  ligeros vs esporádicos y pesados).
- El cliente puede apagar Ollama para usar LLM cloud (Groq / Gemini / OpenAI)
  sin perder la búsqueda semántica.
- Failure isolation: caída de uno no afecta al otro.

Modelo por defecto: ``Snowflake/snowflake-arctic-embed-m-v2.0``
- 768 dim (mismo que ``nomic-embed-text``, no requiere re-indexar Qdrant)
- Apache 2.0, on-prem total
- Entrenado y benchmarkeado en ES/EN/DE/FR/IT
- ~1.2 GB en disco, ~600 MB RAM

Fallback a hash determinístico si TEI no está disponible. El fallback genera
vectores arbitrarios → la búsqueda deja de funcionar para esos candidatos;
loguea un ERROR alto para que sea visible en operaciones.
"""
import hashlib
import logging
import time
from typing import List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Snowflake/snowflake-arctic-embed-m-v2.0 produce vectores de 768 dim.
# Si el modelo cambia, este valor se actualiza solo en el primer embed.
DEFAULT_EMBEDDING_DIM = 768


class EmbeddingService:
    """Cliente HTTP del servicio de embeddings (TEI por defecto).

    El servicio corre en su propio contenedor Docker y es independiente del
    LLM. Cuando ``LLM_PROVIDER`` cambia, este adapter no se afecta.
    """

    # Tiempo de espera tras fallo antes de reintentar conectar.
    # Sin esto, un fallo transitorio caía permanentemente en hash fallback y
    # todos los CVs subsecuentes quedaban indexados con vectores arbitrarios.
    _RETRY_AFTER_SECS = 30

    def __init__(self, host: str = None, model_name: str = None):
        self.host = host or getattr(settings, "EMBEDDINGS_HOST", "http://embeddings:8080")
        self.model_name = model_name or getattr(
            settings, "EMBEDDING_MODEL", "Snowflake/snowflake-arctic-embed-m-v2.0"
        )
        self.dimension = DEFAULT_EMBEDDING_DIM
        self._available: Optional[bool] = None
        self._last_failed_at: float = 0.0
        self._fallback_warned: bool = False
        # Cliente persistente — reutiliza la conexión TCP entre requests.
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

    def _warn_fallback_once(self) -> None:
        """Loguea un ERROR alto la primera vez que se cae al hash fallback.

        El fallback hash genera vectores arbitrarios en el espacio de
        embeddings → Qdrant deja de devolver resultados sensatos para los
        candidatos indexados ahora. Debe ser ruidoso, no silencioso.
        """
        if not self._fallback_warned:
            logger.error(
                "⚠️  Embeddings DEGRADADOS a hash fallback — la búsqueda semántica "
                "NO funcionará para los candidatos indexados ahora. Verifica que "
                "el servicio 'embeddings' (TEI) esté arriba en %s. Reintentando "
                "cada %ss.",
                self.host,
                self._RETRY_AFTER_SECS,
            )
            self._fallback_warned = True

    def _mark_unavailable(self) -> None:
        """Marca el servicio como no disponible y registra el timestamp."""
        self._available = False
        self._last_failed_at = time.time()

    def _is_in_retry_cooldown(self) -> bool:
        """True si hubo un fallo reciente y aún no toca reintentar."""
        if self._available is not False:
            return False
        return (time.time() - self._last_failed_at) < self._RETRY_AFTER_SECS

    async def _check_available(self) -> bool:
        """Verifica salud de TEI vía su endpoint /health.

        Cachea el ``True`` indefinidamente; el ``False`` solo se cachea durante
        ``_RETRY_AFTER_SECS`` para permitir recuperación automática cuando el
        servicio vuelve.
        """
        if self._available is True:
            return True

        if self._is_in_retry_cooldown():
            return False

        try:
            response = await self._client.get(f"{self.host}/health")
            if response.status_code == 200:
                if self._fallback_warned:
                    logger.info(
                        "✅ Embeddings recuperados tras fallback — TEI responde en %s",
                        self.host,
                    )
                    self._fallback_warned = False
                self._available = True
                return True

            logger.warning(
                "⚠️ TEI /health devolvió HTTP %s en %s", response.status_code, self.host
            )
            self._mark_unavailable()
        except Exception as e:
            logger.warning("⚠️ TEI no accesible en %s: %s", self.host, e)
            self._mark_unavailable()

        return False

    async def _tei_embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Genera embeddings para uno o varios textos vía TEI.

        TEI acepta batches nativos. Schema oficial:
            POST /embed  {"inputs": ["t1", "t2", ...]}
            → [[...], [...], ...]
        """
        response = await self._client.post(
            f"{self.host}/embed",
            json={"inputs": texts},
        )
        response.raise_for_status()
        embeddings = response.json()

        # TEI devuelve directamente una lista de listas (no un dict como Ollama).
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise ValueError(
                f"TEI devolvió {type(embeddings).__name__} con "
                f"{len(embeddings) if hasattr(embeddings, '__len__') else '?'} "
                f"vectores, esperábamos {len(texts)}"
            )

        # Auto-detectar la dimensión real del modelo en la primera llamada.
        if embeddings and len(embeddings[0]) != self.dimension:
            self.dimension = len(embeddings[0])
            logger.info("Embedding dimension auto-detectada: %s", self.dimension)

        return embeddings

    def _text_to_hash_vector(self, text: str) -> List[float]:
        """Pseudo-embedding determinístico desde el hash del texto.

        Solo se usa como fallback cuando TEI está caído. Los vectores no tienen
        sentido semántico — sirven únicamente para que el sistema no se rompa
        mientras se recupera el servicio.
        """
        hash_bytes = hashlib.sha384(text.encode("utf-8")).digest()
        vector = []
        for i in range(self.dimension):
            byte_val = hash_bytes[i % len(hash_bytes)]
            vector.append((byte_val / 127.5) - 1.0)
        return vector

    async def embed_text(self, text: str) -> List[float]:
        """Genera embedding para un texto único.

        Usa TEI si está disponible, fallback a hash en caso contrario.
        """
        if not text or not text.strip():
            return [0.0] * self.dimension

        clean_text = text.strip()

        if await self._check_available():
            try:
                vectors = await self._tei_embed_batch([clean_text])
                return vectors[0]
            except Exception as e:
                logger.error("TEI embedding error: %s", e)
                self._mark_unavailable()
                self._warn_fallback_once()
                return self._text_to_hash_vector(clean_text.lower())

        self._warn_fallback_once()
        return self._text_to_hash_vector(clean_text.lower())

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Genera embeddings para múltiples textos en una sola llamada HTTP.

        TEI soporta batching nativo con throughput muy superior al loop
        secuencial: 4 textos cortos toman ~50 ms en CPU vs ~200 ms uno por uno.
        """
        if not texts:
            return []

        clean_texts = [t.strip() if t else "" for t in texts]

        if await self._check_available():
            try:
                return await self._tei_embed_batch(clean_texts)
            except Exception as e:
                logger.error("TEI batch embedding error: %s", e)
                self._mark_unavailable()
                self._warn_fallback_once()
                return [self._text_to_hash_vector(t.lower()) for t in clean_texts]

        self._warn_fallback_once()
        return [
            self._text_to_hash_vector(t.lower()) if t else [0.0] * self.dimension
            for t in clean_texts
        ]

    async def embed_candidate_aspects(
        self,
        experience_text: str,
        education_text: str,
        skills_text: str,
        summary_text: str,
    ) -> dict[str, List[float]]:
        """Embebe los 4 named vectors del candidato en una sola llamada batch."""
        texts = [experience_text, education_text, skills_text, summary_text]
        vectors = await self.embed_batch(texts)
        return {
            "experience": vectors[0],
            "education": vectors[1],
            "skills": vectors[2],
            "summary": vectors[3],
        }

    async def embed_job_aspects(
        self,
        requirements_text: str,
        skills_text: str,
        description_text: str,
    ) -> dict[str, List[float]]:
        """Embebe los aspectos de la vacante."""
        texts = [requirements_text, skills_text, description_text]
        vectors = await self.embed_batch(texts)
        return {
            "requirements": vectors[0],
            "skills": vectors[1],
            "description": vectors[2],
        }

    @property
    def is_semantic(self) -> bool:
        """True si está usando embeddings reales (no el fallback hash)."""
        return self._available is True

    def get_status(self) -> dict:
        """Estado actual del servicio — útil para /health y /ops/observability."""
        return {
            "backend": "text-embeddings-inference (TEI)",
            "host": self.host,
            "model": self.model_name,
            "available": self._available,
            "dimension": self.dimension,
            "semantic": self.is_semantic,
        }
