# Section 6.3: Standalone Image Extractor

import os
import json
import base64
import hashlib
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from ch6.config import config
from ch6.logging import logger, ctx_source_file, ctx_modality, ctx_pipeline_stage
from ch6.models import PerceptionChunk, ModalityType
from ch6.perception.vlm_client import VLMClient

class ImageAnalysisResult(BaseModel):
    """Pydantic model representing structured image analysis output."""
    title: str = Field(..., description="Short descriptive title of the image or card")
    summary: str = Field(..., description="Detailed text summary of the contents and visual details")
    entities: List[str] = Field(default_factory=list, description="Extracted entity names, ID numbers, or key metrics")
    confidence_score: float = Field(default=1.0, description="Estimated confidence score of the VLM analysis")

class ImageExtractor:
    """Extracts structured data from standalone images using VLM analysis and schema validation."""

    def __init__(self) -> None:
        self.vlm_client = VLMClient()

    def _generate_chunk_id(self, filepath: str) -> str:
        """Generates unique chunk ID from file path."""
        return hashlib.md5(filepath.encode()).hexdigest()

    async def extract(self, file_path: str) -> List[PerceptionChunk]:
        """Extracts structured JSON description from a standalone image."""
        ctx_source_file.set(os.path.basename(file_path))
        ctx_modality.set("image")
        ctx_pipeline_stage.set("extraction")

        logger.info("Starting standalone image VLM extraction", file=file_path)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image file not found: {file_path}")

        chunk_id = self._generate_chunk_id(file_path)
        
        # Load image bytes for payload storage
        try:
            with open(file_path, "rb") as f:
                img_bytes = f.read()
            content_b64 = base64.b64encode(img_bytes).decode("utf-8")
        except Exception as e:
            logger.error("Failed to read image file bytes", error=str(e))
            return []

        prompt = (
            "Analyze this image in detail. Extract structured clinical, medication, or insurance card details "
            "into a clean JSON structure containing the title, a comprehensive summary, list of entities (such as Member IDs, Nurse names, Medication lists), "
            "and an estimated confidence score of the VLM extraction."
        )

        try:
            # Enforce JSON output schema via the pydantic class
            vlm_data = await self.vlm_client.analyze_image(
                prompt=prompt,
                image_path=file_path,
                response_schema=ImageAnalysisResult
            )

            # Validate extraction result schema manually if it was returned as raw dict from local Ollama
            if isinstance(vlm_data, dict) and "title" in vlm_data and "summary" in vlm_data:
                structured_data = vlm_data
                confidence = float(vlm_data.get("confidence_score", 1.0))
                content_text = f"Title: {vlm_data['title']}\nSummary: {vlm_data['summary']}\nEntities: {', '.join(vlm_data.get('entities', []))}"
            else:
                # If we parsed a Pydantic model response
                structured_data = vlm_data.model_dump() if hasattr(vlm_data, "model_dump") else dict(vlm_data)
                confidence = float(getattr(vlm_data, "confidence_score", 1.0))
                content_text = f"Title: {getattr(vlm_data, 'title', '')}\nSummary: {getattr(vlm_data, 'summary', '')}\nEntities: {', '.join(getattr(vlm_data, 'entities', []))}"
            
            status = "parsed"

        except Exception as e:
            logger.error(
                "Image VLM analysis or JSON parsing failed. Generating fallback chunk with confidence 0.0.",
                error=str(e)
            )
            # Create a fallback chunk with zero confidence, rather than dropping the image
            structured_data = {"error": f"VLM parse failure: {str(e)}"}
            content_text = f"VLM extraction failed for image: {os.path.basename(file_path)}."
            confidence = 0.0
            status = "failed"

        meta = {
            "layout_type": "standalone_image",
            "vlm_status": status,
            "routing_decision": "vlm_only"
        }

        chunk = PerceptionChunk(
            chunk_id=chunk_id,
            modality=ModalityType.IMAGE,
            source_file=file_path,
            confidence=confidence,
            content_text=content_text,
            content_b64=content_b64,
            structured_data=structured_data,
            metadata=meta
        )

        return [chunk]
