# Section 6.3: Image Extractor Unit Tests

import pytest
from pathlib import Path
from ch6.perception.image import ImageExtractor, ImageAnalysisResult
from ch6.perception.vlm_client import VLMClient
from ch6.models import ModalityType

SAMPLE_DIR = Path("data/samples")

@pytest.mark.asyncio
async def test_image_extractor_success(monkeypatch):
    """Tests image extraction when VLM returns a valid schema object."""
    extractor = ImageExtractor()
    img_path = SAMPLE_DIR / "insurance_card_front.png"
    assert img_path.exists()

    expected_result = ImageAnalysisResult(
        title="Insurance Card Mock",
        summary="A mock health insurance card",
        entities=["Member ID: HFP-98765432-01", "Group Number: GRP-55443"],
        confidence_score=0.95
    )

    # Mock VLMClient analyze_image to return the schema
    async def mock_analyze(*args, **kwargs):
        return expected_result

    monkeypatch.setattr(VLMClient, "analyze_image", mock_analyze)

    chunks = await extractor.extract(str(img_path))
    assert len(chunks) == 1
    chunk = chunks[0]

    assert chunk.modality == ModalityType.IMAGE
    assert chunk.confidence == 0.95
    assert chunk.content_b64 is not None
    assert "Member ID" in chunk.content_text
    assert chunk.structured_data["title"] == "Insurance Card Mock"

@pytest.mark.asyncio
async def test_image_extractor_vlm_failure(monkeypatch):
    """Tests that a VLM failure produces a chunk with confidence=0.0 rather than crash."""
    extractor = ImageExtractor()
    img_path = SAMPLE_DIR / "insurance_card_front.png"

    # Mock VLMClient to raise an exception
    async def mock_analyze_fail(*args, **kwargs):
        raise RuntimeError("VLM API connection timed out")

    monkeypatch.setattr(VLMClient, "analyze_image", mock_analyze_fail)

    chunks = await extractor.extract(str(img_path))
    assert len(chunks) == 1
    chunk = chunks[0]

    assert chunk.modality == ModalityType.IMAGE
    assert chunk.confidence == 0.0
    assert chunk.metadata["vlm_status"] == "failed"
    assert "vlm_fallback_failed" in chunk.structured_data or "error" in chunk.structured_data
