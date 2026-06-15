"""
Qdrant Vector Database Adapter
Handles semantic search and vector storage for candidates.
"""
import logging
from typing import List, Optional, Tuple
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.models import (
    Distance, VectorParams,
    HnswConfigDiff, ScalarQuantizationConfig, ScalarType, ScalarQuantization,
    SearchParams,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


class QdrantRepository:
    """
    Repository for vector operations with Qdrant.
    Implements named vectors for multi-aspect candidate representation.
    """
    
    COLLECTION_NAME = "candidates"
    VECTOR_SIZE = 768  # nomic-embed-text via Ollama
    
    VECTOR_NAMES = ["experience", "education", "skills", "summary"]
    
    def __init__(self, client: Optional[QdrantClient] = None):
        self.client = client or QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.COLLECTION_NAME not in collection_names:
            # Create collection with named vectors + optimized HNSW config.
            # HNSW params based on Qdrant benchmark recommendations for
            # high-precision top-K retrieval (precision > recall tradeoff):
            # - m=16: edges per node, default is fine for this scale
            # - ef_construct=200: higher quality index (default 100), ~2x build time
            #   but significantly better recall at top-20
            # Ref: Qdrant HNSW docs, "Efficient and robust approximate nearest neighbor
            # search using Hierarchical Navigable Small World graphs" (Malkov & Yashunin, 2018)
            hnsw_config = HnswConfigDiff(m=16, ef_construct=200)

            # Scalar quantization: compresses 768-dim float32 vectors to int8.
            # 4x memory reduction with <1% quality loss for nomic-embed-text.
            # Ref: Qdrant quantization docs; "Product Quantization for Nearest Neighbor Search"
            # (Jégou et al., 2011)
            #
            # NOTA: la clase a instanciar es `ScalarQuantization` (envoltorio con el
            # campo `scalar`), NO `QuantizationConfig`. Esto último es un `typing.Union`
            # de qdrant-client (Scalar|Product|Binary) usado solo como type hint —
            # instanciarlo lanza "Cannot instantiate typing.Union". El bug quedaba
            # latente porque este bloque solo corre al CREAR la colección por primera
            # vez (BD vacía); con datos preexistentes nunca se ejecutaba.
            quantization_config = ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,  # preserve 99th percentile range (avoids outlier clipping)
                    always_ram=True,  # keep quantized index in RAM for speed
                )
            )

            vectors_config = {
                name: VectorParams(
                    size=self.VECTOR_SIZE,
                    distance=Distance.COSINE,
                    hnsw_config=hnsw_config,
                )
                for name in self.VECTOR_NAMES
            }

            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=vectors_config,
                quantization_config=quantization_config,
            )
            logger.info(f"Created Qdrant collection: {self.COLLECTION_NAME} (HNSW ef_construct=200, INT8 quantization)")
    
    async def upsert_candidate(
        self,
        candidate_id: UUID,
        vectors: dict[str, List[float]],
        payload: dict
    ) -> None:
        """
        Insert or update a candidate's vectors.
        
        Args:
            candidate_id: Unique candidate identifier
            vectors: Dict mapping vector name to embedding
            payload: Metadata to store with the point
        """
        point = qmodels.PointStruct(
            id=str(candidate_id),
            vector=vectors,
            payload={
                **payload,
                "candidate_id": str(candidate_id),
            }
        )
        
        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[point]
        )
        logger.debug(f"Upserted candidate {candidate_id} to Qdrant")
    
    async def search_similar(
        self,
        query_vector: List[float],
        vector_name: str = "skills",
        limit: int = 20,
        score_threshold: float = 0.5,
        filter_conditions: Optional[dict] = None
    ) -> List[Tuple[str, float, dict]]:
        """
        Search for similar candidates using a single vector.
        
        Returns:
            List of (candidate_id, score, payload) tuples
        """
        qdrant_filter = None
        if filter_conditions:
            qdrant_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key=key,
                        match=qmodels.MatchValue(value=value)
                    )
                    for key, value in filter_conditions.items()
                ]
            )
        
        results = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=query_vector,
            using=vector_name,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=qdrant_filter,
            with_payload=True
        )

        return [
            (point.id, point.score, point.payload)
            for point in results.points
        ]
    
    async def hybrid_search(
        self,
        query_vectors: dict[str, List[float]],
        weights: Optional[dict[str, float]] = None,
        limit: int = 20,
        job_id_filter: Optional[str] = None,
    ) -> List[Tuple[str, float, dict]]:
        """
        Perform hybrid search across multiple named vectors.
        Uses prefetch + fusion strategy.
        
        Args:
            query_vectors: Dict mapping vector name to query embedding
            weights: Optional weights for each vector type
            limit: Maximum results to return
        """
        if weights is None:
            weights = {
                "skills": 0.40,
                "experience": 0.35,
                "education": 0.15,
                "summary": 0.10
            }
        
        # Prefetch from each vector.
        # Overfetch 3x (not 2x) so RRF fusion has a wider candidate pool to rerank.
        # Ref: "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning
        # Methods" (Cormack et al., 2009) — fusion quality improves with larger input lists.
        # hnsw_ef=128: at query time, HNSW explores 128 candidates per hop.
        # Higher ef = better precision at top-K, modest latency cost.
        # Qdrant recommends ef >= 2*limit for reliable top-K recall.
        prefetch_queries = [
            qmodels.Prefetch(
                query=query_vectors.get(name, [0.0] * self.VECTOR_SIZE),
                using=name,
                limit=limit * 3,  # 3x overfetch for better RRF fusion pool
                params=SearchParams(hnsw_ef=max(128, limit * 4)),
            )
            for name in self.VECTOR_NAMES
            if name in query_vectors
        ]
        
        # Build optional job_id filter
        qdrant_filter = None
        if job_id_filter:
            qdrant_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="job_id",
                        match=qmodels.MatchValue(value=job_id_filter)
                    )
                ]
            )

        # Use RRF fusion via Qdrant's query API
        results = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            prefetch=prefetch_queries,
            query=qmodels.FusionQuery(fusion=qmodels.Fusion.RRF),
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True
        )
        
        return [
            (point.id, point.score, point.payload)
            for point in results.points
        ]
    
    async def delete_candidate(self, candidate_id: UUID) -> None:
        """Remove a candidate from the vector store."""
        self.client.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector=qmodels.PointIdsList(
                points=[str(candidate_id)]
            )
        )
        logger.debug(f"Deleted candidate {candidate_id} from Qdrant")
    
    async def get_collection_info(self) -> dict:
        """Get collection statistics."""
        info = self.client.get_collection(self.COLLECTION_NAME)
        status = info.status
        status_val = status.value if hasattr(status, "value") else str(status)
        return {
            "points_count": info.points_count or 0,
            "status": status_val,
        }
