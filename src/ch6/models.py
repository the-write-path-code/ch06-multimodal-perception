# Section 6.1 / 6.5: Grounded Chunks and Handoff Contracts

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

class ModalityType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    TABLE = "table"
    AUDIO = "audio"

class ZoneType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    FIGURE = "figure"

class PerceptionChunk(BaseModel):
    """Grounded representation of a multimodal data extract.

    Every chunk knows its modality, origin, location, and extraction confidence.
    """
    chunk_id: str = Field(..., description="Unique hash or UUID for this chunk")
    modality: ModalityType = Field(..., description="The physical modality of this segment")
    source_file: str = Field(..., description="Path to the originating file")
    page_number: Optional[int] = Field(default=None, description="Page number of the chunk (1-indexed)")
    location: Optional[Dict[str, Any]] = Field(default=None, description="Coordinates, bounding box, or structural indices")
    confidence: float = Field(default=1.0, description="Extraction confidence score (0.0 to 1.0)")
    content_text: Optional[str] = Field(default=None, description="Textual description or direct content text")
    content_b64: Optional[str] = Field(default=None, description="Base64 payload for image-based/VLM ingestion")
    structured_data: Optional[Dict[str, Any]] = Field(default=None, description="Extracted key-value or structured schema fields")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary tracking logging / PII flags")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0 inclusive")
        return v

class EmbeddedChunk(BaseModel):
    """PerceptionChunk enriched with multi-modal vector embeddings."""
    chunk: PerceptionChunk
    dense_vector: Optional[List[float]] = Field(default=None, description="Dense embedding vector")
    sparse_vector: Optional[Dict[str, float]] = Field(default=None, description="Sparse embedding map (index to weight)")

class HandoffPayload(BaseModel):
    """The strict typed payload contract flowing between pipeline stages and agents."""
    chunk: PerceptionChunk
    dense_vector: Optional[List[float]] = Field(default=None, description="Dense embedding vector")
    sparse_vector: Optional[Dict[str, float]] = Field(default=None, description="Sparse embedding map")
    qdrant_point_id: Optional[str] = Field(default=None, description="Vector database point ID")
    validation_status: str = Field(..., description="Contract validation status (e.g. VALID, REVIEW)")
    flags: List[str] = Field(default_factory=list, description="Tracing and audit flags (e.g. PII_DETECTED, LOW_CONFIDENCE)")

class RetrievalResult(BaseModel):
    """Typed result returned from cross-modal retrieval queries."""
    chunk: PerceptionChunk
    score: float
    qdrant_point_id: str
