# Section 6.4: Qdrant Vector Catalog

import uuid
from typing import List, Dict, Any, Optional, Union
from PIL import Image
from qdrant_client import AsyncQdrantClient
from qdrant_client import models

from ch6.config import config
from ch6.logging import logger
from ch6.models import EmbeddedChunk, PerceptionChunk, ModalityType
from ch6.embedding.dense import DenseEncoder
from ch6.embedding.sparse import SparseEncoder

class VectorCatalog:
    """Manages Qdrant vector database collection configuration, upserts, and hybrid RRF search."""

    def __init__(self) -> None:
        if config.qdrant_url == ":memory:":
            self.client = AsyncQdrantClient(location=":memory:")
        else:
            self.client = AsyncQdrantClient(
                url=config.qdrant_url,
                api_key=config.qdrant_api_key
            )
        self.collection_name = config.qdrant_collection
        self.dense_encoder = DenseEncoder()
        self.sparse_encoder = SparseEncoder()

    async def initialize(self) -> None:
        """Initializes the named Qdrant collection with dense and optional sparse vector spaces."""
        logger.info("Initializing Qdrant Vector Catalog", collection=self.collection_name)
        
        # Check if collection exists
        collections = await self.client.get_collections()
        exists = any(col.name == self.collection_name for col in collections.collections)

        if not exists:
            # 512 dimensions for clip-ViT-B-32 COSINE distance
            vectors_config = {
                "dense": models.VectorParams(
                    size=512,
                    distance=models.Distance.COSINE
                )
            }
            
            sparse_config = None
            if config.enable_sparse_embeddings:
                sparse_config = {
                    "sparse": models.SparseVectorParams(
                        index=models.SparseIndexParams(
                            on_disk=True
                        )
                    )
                }

            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=vectors_config,
                sparse_vectors_config=sparse_config
            )
            logger.info("Created Qdrant collection successfully", collection=self.collection_name)
        else:
            logger.info("Qdrant collection already exists", collection=self.collection_name)

    def _get_qdrant_point_id(self, chunk_id: str) -> str:
        """Generates a stable UUID string from the chunk_id hash for Qdrant compatibility."""
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))

    async def upsert_chunks(self, embedded_chunks: List[EmbeddedChunk]) -> List[str]:
        """Upserts a list of embedded chunks to Qdrant. Returns Qdrant point IDs."""
        points = []
        point_ids = []

        for ec in embedded_chunks:
            chunk = ec.chunk
            pt_id = self._get_qdrant_point_id(chunk.chunk_id)
            point_ids.append(pt_id)

            # Build vectors dict
            vectors: Dict[str, Any] = {}
            if ec.dense_vector:
                vectors["dense"] = ec.dense_vector
            if config.enable_sparse_embeddings and ec.sparse_vector:
                vectors["sparse"] = models.SparseVector(
                    indices=ec.sparse_vector.indices,
                    values=ec.sparse_vector.values
                )

            # Build payload
            payload = {
                "chunk_id": chunk.chunk_id,
                "modality": chunk.modality.value,
                "source_file": chunk.source_file,
                "page_number": chunk.page_number,
                "confidence": chunk.confidence,
                "content_text": chunk.content_text,
                "structured_data": chunk.structured_data,
                "metadata": chunk.metadata
            }

            points.append(
                models.PointStruct(
                    id=pt_id,
                    vector=vectors,
                    payload=payload
                )
            )

        if points:
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.info("Upserted chunks to Qdrant successfully", count=len(points))

        return point_ids

    async def search(
        self,
        text_query: Optional[str] = None,
        image_query: Optional[Image.Image] = None,
        top_k: int = 5,
        filter_modality: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Executes a hybrid RRF search (text) or cross-modal dense search (image)."""
        
        # Build query filters
        query_filter = None
        if filter_modality:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="modality",
                        match=models.MatchValue(value=filter_modality)
                    )
                ]
            )

        # 1. Text Query: Hybrid dense + sparse search with RRF Fusion
        if text_query:
            # Generate query embeddings
            dense_vectors = self.dense_encoder.embed_text([text_query])
            dense_query = dense_vectors[0]

            if config.enable_sparse_embeddings:
                sparse_vectors = self.sparse_encoder.embed_text([text_query])
                sparse_query = sparse_vectors[0]

                # Setup RRF Fusion prefetch requests
                prefetch_dense = models.Prefetch(
                    query=dense_query,
                    using="dense",
                    filter=query_filter,
                    limit=top_k * 2
                )
                prefetch_sparse = models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_query["indices"],
                        values=sparse_query["values"]
                    ),
                    using="sparse",
                    filter=query_filter,
                    limit=top_k * 2
                )

                # Fuse and query points
                results = await self.client.query_points(
                    collection_name=self.collection_name,
                    prefetch=[prefetch_dense, prefetch_sparse],
                    query=models.FusionQuery(
                        fusion=models.Fusion.RRF
                    ),
                    query_filter=query_filter,
                    limit=top_k
                )
            else:
                # Dense-only query search
                results = await self.client.query_points(
                    collection_name=self.collection_name,
                    query=dense_query,
                    using="dense",
                    query_filter=query_filter,
                    limit=top_k
                )

        # 2. Image Query: Dense visual search
        elif image_query:
            dense_vectors = self.dense_encoder.embed_image([image_query])
            dense_query = dense_vectors[0]

            results = await self.client.query_points(
                collection_name=self.collection_name,
                query=dense_query,
                using="dense",
                query_filter=query_filter,
                limit=top_k
            )
        else:
            raise ValueError("Must provide either text_query or image_query")

        # 3. Format outputs
        output = []
        for pt in results.points:
            payload = pt.payload or {}
            output.append({
                "qdrant_point_id": str(pt.id),
                "score": pt.score,
                "payload": payload
            })

        return output
