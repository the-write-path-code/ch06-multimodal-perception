# Section 6.5: Handoff Contract Verification

from typing import List
from ch6.config import config
from ch6.logging import logger
from ch6.models import PerceptionChunk, EmbeddedChunk, HandoffPayload

class HandoffVerifier:
    """Verifies that processed multimodal chunks satisfy downstream ingestion contracts."""

    def __init__(self) -> None:
        self.high_conf = config.high_confidence_threshold
        self.low_conf = config.low_confidence_threshold

    def verify_contract(self, embedded_chunk: EmbeddedChunk) -> HandoffPayload:
        """Verifies if the embedded chunk meets confidence and privacy/redaction requirements.

        Flags chunks for human review if:
        1. Confidence is below low_confidence_threshold.
        2. Sensitivity scanner marked PII/PHI as detected (pii_detected = True).
        """
        chunk = embedded_chunk.chunk
        flags: List[str] = []
        validation_status = "VALID"

        # Check confidence boundaries
        if chunk.confidence < self.low_conf:
            flags.append("LOW_CONFIDENCE")
            validation_status = "REVIEW"
            logger.warn(
                "Chunk failed confidence contract. Flagged for review.",
                chunk_id=chunk.chunk_id,
                confidence=chunk.confidence,
                threshold=self.low_conf
            )
        elif chunk.confidence >= self.high_conf:
            flags.append("HIGH_CONFIDENCE")

        # Check PII/PHI detection metadata status
        pii_detected = chunk.metadata.get("pii_detected", False)
        if pii_detected:
            flags.append("PII_DETECTED")
            validation_status = "REVIEW"
            logger.warn(
                "Chunk contains sensitive PII/PHI data. Flagged for review.",
                chunk_id=chunk.chunk_id
            )

        payload = HandoffPayload(
            chunk=chunk,
            dense_vector=embedded_chunk.dense_vector,
            sparse_vector=embedded_chunk.sparse_vector,
            qdrant_point_id=None,
            validation_status=validation_status,
            flags=flags
        )

        return payload
