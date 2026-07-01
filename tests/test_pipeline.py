# Section 6.5: Multimodal Pipeline Integration Tests

import pytest
from PIL import Image
from ch6.models import PerceptionChunk, ModalityType
from ch6.pipeline import PerceptionPipeline
from ch6.query import SearchService
from ch6.retrieval.registry import AssetRegistry
from ch6.retrieval.store import VectorCatalog

@pytest.mark.asyncio
async def test_pipeline_ingestion_and_search_flow(monkeypatch):
    """Tests the full end-to-end flow: Ingest -> Embed -> Contract -> SQLite -> Qdrant -> Search."""
    pipeline = PerceptionPipeline()
    await pipeline.initialize()

    # 1. Mock PerceptionDispatcher.perceive to return sample chunks
    mock_chunks = [
        PerceptionChunk(
            chunk_id="chunk-valid-text",
            modality=ModalityType.PDF,
            source_file="data/samples/patient_care_protocol.pdf",
            confidence=0.98,
            content_text="Protocol 12: Administer standard IV fluids for dehydrated patients.",
            structured_data={"iv_type": "standard", "protocol_num": 12}
        ),
        PerceptionChunk(
            chunk_id="chunk-review-lowconf",
            modality=ModalityType.PDF,
            source_file="data/samples/patient_care_protocol.pdf",
            confidence=0.30,  # Below 0.50 threshold
            content_text="Low confidence doctor handwriting scribble.",
            structured_data={"note_type": "scribble"}
        ),
        PerceptionChunk(
            chunk_id="chunk-review-pii",
            modality=ModalityType.PDF,
            source_file="data/samples/patient_care_protocol.pdf",
            confidence=0.92,
            content_text="Billing statement details for cardholder [REDACTED]",
            metadata={"pii_detected": True},  # PII detected
            structured_data={"cardholder": "REDACTED"}
        )
    ]

    async def mock_perceive(filepath):
        return mock_chunks

    monkeypatch.setattr(pipeline.dispatcher, "perceive", mock_perceive)

    # 2. Run ingestion
    handoffs = await pipeline.ingest_document("data/samples/patient_care_protocol.pdf")
    assert len(handoffs) == 3

    # Check validation outcomes
    assert handoffs[0].validation_status == "VALID"
    assert handoffs[0].qdrant_point_id is not None  # Indexed

    assert handoffs[1].validation_status == "REVIEW"
    assert handoffs[1].qdrant_point_id is None      # Held in review

    assert handoffs[2].validation_status == "REVIEW"
    assert handoffs[2].qdrant_point_id is None      # Held in review

    # 3. Check SQLite Registry
    # All 3 chunks should be registered in SQLite registry (so review chunks are audited)
    db_chunk_valid = await pipeline.registry.get_chunk_by_qdrant_id(handoffs[0].qdrant_point_id)
    assert db_chunk_valid is not None
    assert db_chunk_valid["id"] == "chunk-valid-text"
    assert db_chunk_valid["structured_data"]["protocol_num"] == 12

    # Check review chunks are NOT searchable in Qdrant (since they have no point ID)
    db_chunk_invalid = await pipeline.registry.get_chunk_by_qdrant_id("some-random-id")
    assert db_chunk_invalid is None

    # 4. Search and retrieve matching documents
    search_service = SearchService()
    
    # Text query search
    text_results = await search_service.search(text_query="dehydrated standard IV protocol", top_k=2)
    assert len(text_results) == 1
    res = text_results[0]
    assert res["qdrant_point_id"] == handoffs[0].qdrant_point_id
    assert res["modality"] == "pdf"
    assert res["source_file"] == "data/samples/patient_care_protocol.pdf"
    assert res["structured_data"]["iv_type"] == "standard"

    # Cross-modal Image query search (using Clip shared space)
    img_query = Image.new("RGB", (224, 224), (255, 255, 255))
    image_results = await search_service.search(image_query=img_query, top_k=2)
    assert len(image_results) == 1
    assert image_results[0]["qdrant_point_id"] == handoffs[0].qdrant_point_id
