# Section 6.4: Retrieval Integration Tests

import pytest
from pathlib import Path
from PIL import Image
from ch6.config import config
from ch6.models import PerceptionChunk, EmbeddedChunk, ModalityType
from ch6.retrieval.registry import AssetRegistry
from ch6.retrieval.store import VectorCatalog
from ch6.embedding.dense import DenseEncoder
from ch6.embedding.sparse import SparseEncoder

SAMPLE_DIR = Path("data/samples")

@pytest.mark.asyncio
async def test_sqlite_asset_registry():
    """Tests SQLite AssetRegistry creation, registration, and retrievals."""
    registry = AssetRegistry()
    await registry.initialize()

    # Register document
    doc_id = "doc-uuid-1"
    await registry.register_document(doc_id, "data/samples/protocol.pdf", "pdf")

    # Register chunk
    chunk_id = "chunk-uuid-1"
    await registry.register_chunk(
        doc_id=doc_id,
        chunk_id=chunk_id,
        modality="pdf",
        page_number=2,
        qdrant_point_id="point-uuid-1",
        content_preview="Assessment protocols list",
        metadata={"pii_detected": False},
        structured_data={"limits": "2 hours"}
    )

    # Retrieve and check
    chunk = await registry.get_chunk_by_qdrant_id("point-uuid-1")
    assert chunk is not None
    assert chunk["id"] == chunk_id
    assert chunk["modality"] == "pdf"
    assert chunk["page_number"] == 2
    assert chunk["metadata"]["pii_detected"] is False
    assert chunk["structured_data"]["limits"] == "2 hours"

@pytest.mark.asyncio
async def test_qdrant_vector_store_operations():
    """Tests collection initialization, upserting chunks, and search retrievals in-memory."""
    # Ensure config sets in-memory
    assert config.qdrant_url == ":memory:"

    catalog = VectorCatalog()
    await catalog.initialize()

    dense = DenseEncoder()
    sparse = SparseEncoder()

    # 1. Create a dummy chunk to index
    chunk = PerceptionChunk(
        chunk_id="chunk-test-1",
        modality=ModalityType.IMAGE,
        source_file="data/samples/insurance_card_front.png",
        confidence=0.95,
        content_text="Title: Insurance Card. Member ID: HFP-12345.",
        structured_data={"member_id": "HFP-12345", "copay": 20}
    )

    # Embed
    text_content = chunk.content_text
    dense_vec = dense.embed_text([text_content])[0]
    sparse_vec = sparse.embed_text([text_content])[0]

    ec = EmbeddedChunk(
        chunk=chunk,
        dense_vector=dense_vec,
        sparse_vector=sparse_vec
    )

    # Upsert
    point_ids = await catalog.upsert_chunks([ec])
    assert len(point_ids) == 1
    pt_id = point_ids[0]

    # 2. Text Search Retrieval
    search_results = await catalog.search(text_query="insurance copay", top_k=2)
    assert len(search_results) == 1
    res = search_results[0]
    assert res["qdrant_point_id"] == pt_id
    assert res["payload"]["structured_data"]["member_id"] == "HFP-12345"

    # 3. Filtered Search by modality
    # Should find it when filtering by image
    res_img = await catalog.search(text_query="insurance", filter_modality="image", top_k=2)
    assert len(res_img) == 1
    
    # Should not find it when filtering by audio
    res_aud = await catalog.search(text_query="insurance", filter_modality="audio", top_k=2)
    assert len(res_aud) == 0

    # 4. Cross-modal Image Search
    img_query = Image.new("RGB", (100, 100), (50, 100, 200))
    res_cross = await catalog.search(image_query=img_query, top_k=2)
    assert len(res_cross) == 1
    assert res_cross[0]["qdrant_point_id"] == pt_id
