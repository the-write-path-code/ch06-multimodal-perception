# Section 6.5: Multimodal Perception Pipeline

import io
import uuid
import base64
import asyncio
from pathlib import Path
from typing import List, Optional
from PIL import Image

from ch6.config import config
from ch6.logging import logger
from ch6.models import PerceptionChunk, EmbeddedChunk, HandoffPayload, ModalityType
from ch6.perception.dispatcher import PerceptionDispatcher
from ch6.embedding.dense import DenseEncoder
from ch6.embedding.sparse import SparseEncoder
from ch6.retrieval.registry import AssetRegistry
from ch6.retrieval.store import VectorCatalog
from ch6.contracts.handoff import HandoffVerifier

class PerceptionPipeline:
    """Orchestrates document extraction, multi-modal embedding, metadata registering, and vector database catalog indexing."""

    def __init__(self) -> None:
        self.dispatcher = PerceptionDispatcher()
        self.dense_encoder = DenseEncoder()
        self.sparse_encoder = SparseEncoder()
        self.registry = AssetRegistry()
        self.catalog = VectorCatalog()
        self.verifier = HandoffVerifier()
        self.semaphore = asyncio.Semaphore(config.pipeline_concurrency)

    async def initialize(self) -> None:
        """Initializes both SQLite registry and Qdrant collections."""
        await self.registry.initialize()
        await self.catalog.initialize()

    def _decode_image_payload(self, b64_str: str) -> Image.Image:
        """Decodes base64 string payload to a PIL Image object."""
        img_bytes = base64.b64decode(b64_str)
        return Image.open(io.BytesIO(img_bytes)).convert("RGB")

    async def process_chunk(self, chunk: PerceptionChunk, doc_id: str) -> HandoffPayload:
        """Processes a single perception chunk through embedding, verification, and database registering."""
        async with self.semaphore:
            logger.info("Processing chunk through pipeline", chunk_id=chunk.chunk_id, modality=chunk.modality.value)

            # 1. Compute dense cross-modal embeddings
            dense_vector: Optional[List[float]] = None
            if chunk.modality == ModalityType.IMAGE and chunk.content_b64:
                try:
                    img = self._decode_image_payload(chunk.content_b64)
                    dense_vector = self.dense_encoder.embed_image([img])[0]
                except Exception as e:
                    logger.error("Failed to embed image payload. Falling back to text.", chunk_id=chunk.chunk_id, error=str(e))
                    dense_vector = self.dense_encoder.embed_text([chunk.content_text])[0]
            else:
                dense_vector = self.dense_encoder.embed_text([chunk.content_text])[0]

            # 2. Compute sparse keyword embeddings
            sparse_vector = None
            if config.enable_sparse_embeddings:
                sparse_vector = self.sparse_encoder.embed_text([chunk.content_text])[0]

            # 3. Create embedded representation
            embedded = EmbeddedChunk(
                chunk=chunk,
                dense_vector=dense_vector,
                sparse_vector=sparse_vector
            )

            # 4. Run handoff contract check
            payload = self.verifier.verify_contract(embedded)

            # 5. SQLite Registry Save
            await self.registry.register_chunk(
                doc_id=doc_id,
                chunk_id=chunk.chunk_id,
                modality=chunk.modality.value,
                page_number=chunk.page_number,
                qdrant_point_id=None,
                content_preview=chunk.content_text[:200],
                metadata=chunk.metadata,
                structured_data=chunk.structured_data
            )

            # 6. Index into Qdrant only if contract is VALID
            if payload.validation_status == "VALID":
                qdrant_ids = await self.catalog.upsert_chunks([embedded])
                if qdrant_ids:
                    pt_id = qdrant_ids[0]
                    payload.qdrant_point_id = pt_id
                    # Update SQLite chunk table with Qdrant reference ID
                    await self.registry.register_chunk(
                        doc_id=doc_id,
                        chunk_id=chunk.chunk_id,
                        modality=chunk.modality.value,
                        page_number=chunk.page_number,
                        qdrant_point_id=pt_id,
                        content_preview=chunk.content_text[:200],
                        metadata=chunk.metadata,
                        structured_data=chunk.structured_data
                    )
                    logger.info("Indexed chunk in vector catalog", chunk_id=chunk.chunk_id, qdrant_point_id=pt_id)
            else:
                logger.warn("Chunk held in review queue (skipped vector indexing)", chunk_id=chunk.chunk_id, validation_status=payload.validation_status)

            return payload

    def _detect_modality(self, filepath: str) -> ModalityType:
        """Helper to map file extensions to ModalityType."""
        _, ext = Path(filepath).suffix.lower(), None
        ext = Path(filepath).suffix.lower()
        if ext == ".pdf":
            return ModalityType.PDF
        elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
            return ModalityType.IMAGE
        elif ext in [".csv", ".xlsx", ".xls"]:
            return ModalityType.TABLE
        elif ext in [".wav", ".mp3", ".m4a"]:
            return ModalityType.AUDIO
        return ModalityType.TEXT

    async def ingest_document(self, filepath: str) -> List[HandoffPayload]:
        """Ingests a file end-to-end through dispatcher, embedding, contract check, registry, and catalog."""
        path_obj = Path(filepath)
        if not path_obj.exists():
            raise FileNotFoundError(f"Source file not found: {filepath}")

        # 1. Register document in SQLite
        doc_id = str(uuid.uuid4())
        logger.info("Registering document in asset registry", filepath=filepath, doc_id=doc_id)
        
        # Deduce modality
        modality = self._detect_modality(filepath)
        await self.registry.register_document(doc_id, filepath, modality.value)

        # 2. Extract perception chunks
        logger.info("Running extraction dispatcher", filepath=filepath, modality=modality.value)
        chunks = await self.dispatcher.perceive(filepath)
        
        if not chunks:
            logger.warn("No chunks extracted from document", filepath=filepath)
            return []

        # 3. Process chunks concurrently
        tasks = [self.process_chunk(chunk, doc_id) for chunk in chunks]
        handoffs = await asyncio.gather(*tasks)

        logger.info("Ingestion pipeline finished successfully", filepath=filepath, total_chunks=len(handoffs))
        return handoffs
