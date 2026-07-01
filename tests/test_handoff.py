# Section 6.5: Handoff Contract Verification Tests

import pytest
from ch6.models import PerceptionChunk, EmbeddedChunk, ModalityType
from ch6.contracts.handoff import HandoffVerifier

def test_handoff_verifier_valid_high_confidence():
    """Checks that a high-confidence, clean chunk is marked as VALID with HIGH_CONFIDENCE flag."""
    verifier = HandoffVerifier()
    
    chunk = PerceptionChunk(
        chunk_id="chunk-1",
        modality=ModalityType.PDF,
        source_file="protocol.txt",
        confidence=0.90,
        content_text="This is a safe, clean health directive text chunk."
    )
    ec = EmbeddedChunk(chunk=chunk, dense_vector=[0.1]*512)
    
    payload = verifier.verify_contract(ec)
    assert payload.validation_status == "VALID"
    assert "HIGH_CONFIDENCE" in payload.flags
    assert "PII_DETECTED" not in payload.flags
    assert "LOW_CONFIDENCE" not in payload.flags

def test_handoff_verifier_low_confidence():
    """Checks that a low-confidence chunk is marked as REVIEW with LOW_CONFIDENCE flag."""
    verifier = HandoffVerifier()
    
    # Low confidence chunk (<0.50 default threshold)
    chunk = PerceptionChunk(
        chunk_id="chunk-2",
        modality=ModalityType.PDF,
        source_file="protocol.txt",
        confidence=0.35,
        content_text="Low confidence extracted note."
    )
    ec = EmbeddedChunk(chunk=chunk, dense_vector=[0.1]*512)
    
    payload = verifier.verify_contract(ec)
    assert payload.validation_status == "REVIEW"
    assert "LOW_CONFIDENCE" in payload.flags
    assert "HIGH_CONFIDENCE" not in payload.flags

def test_handoff_verifier_pii_detected():
    """Checks that a chunk containing detected PII is marked as REVIEW with PII_DETECTED flag."""
    verifier = HandoffVerifier()
    
    chunk = PerceptionChunk(
        chunk_id="chunk-3",
        modality=ModalityType.PDF,
        source_file="protocol.txt",
        confidence=0.92,
        content_text="Cardholder John Doe [REDACTED]",
        metadata={"pii_detected": True}
    )
    ec = EmbeddedChunk(chunk=chunk, dense_vector=[0.1]*512)
    
    payload = verifier.verify_contract(ec)
    assert payload.validation_status == "REVIEW"
    assert "PII_DETECTED" in payload.flags
    assert "HIGH_CONFIDENCE" in payload.flags  # Can have both flags
