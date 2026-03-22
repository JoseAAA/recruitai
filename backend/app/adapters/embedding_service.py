"""
Embedding Service Adapter
Generates semantic embeddings using Ollama (local, private).

Uses Ollama's embedding API with nomic-embed-text by default.
Fallback to hash-based embeddings if Ollama is not available.
"""
import logging
import hashlib
from typing import List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# nomic-embed-text produces 768-dim vectors
# If model changes, this auto-updates on first call
DEFAULT_EMBEDDING_DIM = 768


class EmbeddingService:
    """
    Semantic embedding service using Ollama (100% local).
    
    Uses Ollama's /api/embed endpoint with configurable models:
    - nomic-embed-text (default, 768d, 274MB, multilingual)
    - snowflake-arctic-embed2 (alternative, 768d, 568MB)
    
    Falls back to hash-based embeddings if Ollama is unavailable.
    """
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or getattr(settings, 'EMBEDDING_MODEL', 'nomic-embed-text')
        self.ollama_host = getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434')
        self.dimension = DEFAULT_EMBEDDING_DIM
        self._available: Optional[bool] = None
    
    async def _check_available(self) -> bool:
        """Check if Ollama embedding model is available."""
        if self._available is not None:
            return self._available
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_host}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    # Check exact match or match without tag
                    for name in model_names:
                        if self.model_name in name:
                            self._available = True
                            logger.info(f"✅ Ollama embedding model available: {name}")
                            return True
                    
                    logger.warning(
                        f"⚠️ Embedding model '{self.model_name}' not found in Ollama. "
                        f"Available: {model_names}. Run: ollama pull {self.model_name}"
                    )
            self._available = False
        except Exception as e:
            logger.warning(f"⚠️ Ollama not reachable for embeddings: {e}")
            self._available = False
        
        return self._available
    
    async def _ollama_embed(self, text: str) -> List[float]:
        """Generate embedding via Ollama API."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.ollama_host}/api/embed",
                json={
                    "model": self.model_name,
                    "input": text,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Ollama returns {"embeddings": [[...vector...]]}
            embeddings = data.get("embeddings", [])
            if embeddings and len(embeddings) > 0:
                vector = embeddings[0]
                # Update dimension on first successful call
                if len(vector) != self.dimension:
                    self.dimension = len(vector)
                    logger.info(f"Embedding dimension updated to {self.dimension}")
                return vector
            
            raise ValueError("Empty embedding response from Ollama")
    
    async def _ollama_embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts via Ollama API."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.ollama_host}/api/embed",
                json={
                    "model": self.model_name,
                    "input": texts,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            embeddings = data.get("embeddings", [])
            if embeddings and len(embeddings) == len(texts):
                if len(embeddings[0]) != self.dimension:
                    self.dimension = len(embeddings[0])
                return embeddings
            
            raise ValueError(f"Expected {len(texts)} embeddings, got {len(embeddings)}")
    
    def _text_to_hash_vector(self, text: str) -> List[float]:
        """
        Deterministic pseudo-embedding from text hash.
        Fallback when Ollama unavailable.
        """
        hash_bytes = hashlib.sha384(text.encode('utf-8')).digest()
        vector = []
        for i in range(self.dimension):
            byte_val = hash_bytes[i % len(hash_bytes)]
            vector.append((byte_val / 127.5) - 1.0)
        return vector
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        Uses Ollama if available, otherwise hash fallback.
        """
        if not text or not text.strip():
            return [0.0] * self.dimension
        
        clean_text = text.strip()
        
        if await self._check_available():
            try:
                return await self._ollama_embed(clean_text)
            except Exception as e:
                logger.error(f"Ollama embedding error: {e}")
                return self._text_to_hash_vector(clean_text.lower())
        
        return self._text_to_hash_vector(clean_text.lower())
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently."""
        if not texts:
            return []
        
        clean_texts = [t.strip() if t else "" for t in texts]
        
        if await self._check_available():
            try:
                return await self._ollama_embed_batch(clean_texts)
            except Exception as e:
                logger.error(f"Ollama batch embedding error: {e}")
                return [self._text_to_hash_vector(t.lower()) for t in clean_texts]
        
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
        """
        Generate separate embeddings for different candidate aspects.
        Uses a single batch API call for efficiency.
        """
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
        """Generate separate embeddings for job profile aspects."""
        return {
            "requirements": await self.embed_text(requirements_text),
            "skills": await self.embed_text(skills_text),
            "description": await self.embed_text(description_text),
        }
    
    @property
    def is_semantic(self) -> bool:
        """Check if using real semantic embeddings (not hash fallback)."""
        return self._available is True
    
    def get_status(self) -> dict:
        """Get embedding service status."""
        return {
            "model": self.model_name,
            "ollama_host": self.ollama_host,
            "available": self._available,
            "dimension": self.dimension,
            "semantic": self.is_semantic,
        }
