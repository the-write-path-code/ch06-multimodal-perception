# Section 6.5: Model Schema & Validation Unit Tests

import pytest
from pydantic import ValidationError
from ch6.models import ModalityType, PerceptionChunk, HandoffPayload

def test_perception_chunk_validation():
    """Tests that valid PerceptionChunk builds successfully, and incorrect bounds raise ValidationError."""
    # Valid
    chunk = PerceptionChunk(
        chunk_id="chunk-123",
        modality=ModalityType.PDF,
        source_file="/path/to/doc.pdf",
        page_number=1,
        confidence=0.92,
        content_text="Hello nurse visit note."
    )
    assert chunk.chunk_id == "chunk-123"
    assert chunk.confidence == 0.92

    # Invalid confidence (greater than 1.0)
    with pytest.raises(ValidationError):
        PerceptionChunk(
            chunk_id="chunk-123",
            modality=ModalityType.PDF,
            source_file="/path/to/doc.pdf",
            confidence=1.5
        )

    # Invalid confidence (less than 0.0)
    with pytest.raises(ValidationError):
        PerceptionChunk(
            chunk_id="chunk-123",
            modality=ModalityType.PDF,
            source_file="/path/to/doc.pdf",
            confidence=-0.1
        )

def test_handoff_payload_contract():
    """Tests that HandoffPayload enforces metadata tracing requirements."""
    chunk = PerceptionChunk(
        chunk_id="chunk-123",
        modality=ModalityType.AUDIO,
        source_file="/path/to/audio.wav",
        confidence=0.88,
        content_text="Transcribed voice entry text."
    )

    # Valid Handoff
    payload = HandoffPayload(
        chunk=chunk,
        validation_status="VALID",
        flags=["STABLE"]
    )
    assert payload.chunk.chunk_id == "chunk-123"
    assert payload.validation_status == "VALID"

    # Invalid payload (missing required field validation_status)
    with pytest.raises(ValidationError):
        HandoffPayload(chunk=chunk) # type: ignore
