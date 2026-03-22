"""
Qdrant Vector Database Adapter
Handles semantic search and vector storage for candidates.
"""
import logging
from typing import List, Optional, Tuple
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.models import Distance, VectorParams

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
            # Create collection with named vectors
            vectors_config = {
                name: VectorParams(
                    size=self.VECTOR_SIZE,
                    distance=Distance.COSINE
                )
                for name in self.VECTOR_NAMES
            }
            
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=vectors_config,
            )
            logger.info(f"Created Qdrant collection: {self.COLLECTION_NAME}")
    
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
        
        # Prefetch from each vector
        prefetch_queries = [
            qmodels.Prefetch(
                query=query_vectors.get(name, [0.0] * self.VECTOR_SIZE),
                using=name,
                limit=limit * 2  # Overfetch for better fusion
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
