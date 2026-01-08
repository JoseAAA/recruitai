"""
Embedding Service Adapter
Generates semantic embeddings for candidate and job matching.
Uses sentence-transformers for high-quality embeddings with fallback to mock.
"""
import logging
from typing import List, Optional
import hashlib
import os

logger = logging.getLogger(__name__)

# Embedding dimension for all-MiniLM-L6-v2
EMBEDDING_DIM = 384


class EmbeddingService:
    """
    Semantic embedding service for CV and job matching.
    
    Uses sentence-transformers locally (free, private) with automatic
    fallback to hash-based embeddings if model loading fails.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding service.
        
        Args:
            model_name: HuggingFace model name for sentence-transformers
        """
        self.model_name = model_name
        self.dimension = EMBEDDING_DIM
        self._model = None
        self._use_real_embeddings = False
        
        # Try to load real embeddings model
        self._initialize_model()
    
    def _initialize_model(self):
        """Attempt to load sentence-transformers model."""
        try:
            # Suppress tokenizers warning
            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._use_real_embeddings = True
            logger.info(f"✅ EmbeddingService initialized with {self.model_name} (semantic embeddings)")
        except ImportError:
            logger.warning("sentence-transformers not installed, using hash-based fallback")
            self._use_real_embeddings = False
        except Exception as e:
            logger.warning(f"Could not load embedding model: {e}. Using fallback.")
            self._use_real_embeddings = False
        
        if not self._use_real_embeddings:
            logger.info("📋 EmbeddingService using hash-based embeddings (install sentence-transformers for better matching)")
    
    def _text_to_hash_vector(self, text: str) -> List[float]:
        """
        Generate deterministic pseudo-embedding from text hash.
        Fallback when real embeddings unavailable.
        """
        hash_bytes = hashlib.sha384(text.encode('utf-8')).digest()
        vector = []
        for i in range(EMBEDDING_DIM):
            byte_val = hash_bytes[i % len(hash_bytes)]
            vector.append((byte_val / 127.5) - 1.0)
        return vector
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Uses real sentence-transformers if available,
        otherwise falls back to hash-based embeddings.
        """
        if not text or not text.strip():
            return [0.0] * EMBEDDING_DIM
        
        clean_text = text.strip()
        
        if self._use_real_embeddings and self._model is not None:
            try:
                embedding = self._model.encode(clean_text, convert_to_numpy=True)
                return embedding.tolist()
            except Exception as e:
                logger.error(f"Embedding error: {e}")
                return self._text_to_hash_vector(clean_text.lower())
        
        return self._text_to_hash_vector(clean_text.lower())
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.
        Uses batched encoding for real embeddings.
        """
        if not texts:
            return []
        
        clean_texts = [t.strip() if t else "" for t in texts]
        
        if self._use_real_embeddings and self._model is not None:
            try:
                embeddings = self._model.encode(clean_texts, convert_to_numpy=True)
                return embeddings.tolist()
            except Exception as e:
                logger.error(f"Batch embedding error: {e}")
                return [self._text_to_hash_vector(t.lower()) for t in clean_texts]
        
        return [self._text_to_hash_vector(t.lower()) if t else [0.0] * EMBEDDING_DIM for t in clean_texts]
    
    def embed_candidate_aspects(
        self,
        experience_text: str,
        education_text: str,
        skills_text: str,
        summary_text: str,
    ) -> dict[str, List[float]]:
        """
        Generate separate embeddings for different candidate aspects.
        
        Returns dict with keys: experience, education, skills, summary
        
        This multi-aspect approach enables more precise matching:
        - skills: weighted heavily for technical fit
        - experience: for seniority and domain match
        - education: for qualification verification
        - summary: for overall profile similarity
        """
        return {
            "experience": self.embed_text(experience_text),
            "education": self.embed_text(education_text),
            "skills": self.embed_text(skills_text),
            "summary": self.embed_text(summary_text),
        }
    
    def embed_job_aspects(
        self,
        requirements_text: str,
        skills_text: str,
        description_text: str,
    ) -> dict[str, List[float]]:
        """
        Generate separate embeddings for job profile aspects.
        
        Enables targeted matching against candidate vectors.
        """
        return {
            "requirements": self.embed_text(requirements_text),
            "skills": self.embed_text(skills_text),
            "description": self.embed_text(description_text),
        }
    
    @property
    def is_semantic(self) -> bool:
        """Check if using real semantic embeddings."""
        return self._use_real_embeddings
    
    def get_status(self) -> dict:
        """Get embedding service status for debugging."""
        return {
            "model": self.model_name if self._use_real_embeddings else "hash-fallback",
            "semantic": self._use_real_embeddings,
            "dimension": EMBEDDING_DIM,
        }
