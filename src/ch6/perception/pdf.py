# Section 6.1 / 6.3: PDF Extractor with Layout Detection and Confidence Routing

import os
import uuid
import base64
import hashlib
from io import BytesIO
from typing import List, Dict, Any, Optional
from PIL import Image
import pypdfium2 as pdfium
from docling.document_converter import DocumentConverter

from ch6.config import config
from ch6.logging import logger, ctx_correlation_id, ctx_modality, ctx_source_file, ctx_pipeline_stage
from ch6.models import PerceptionChunk, ModalityType
from ch6.perception.vlm_client import VLMClient
from ch6.perception.sensitivity import SensitivityScanner

class PDFExtractor:
    """Extracts text, tables, and figures from PDFs using layout detection & confidence routing."""

    def __init__(self) -> None:
        self.converter = DocumentConverter()
        self.vlm_client = VLMClient()
        self.sensitivity_scanner = SensitivityScanner()

    def _generate_chunk_id(self, filepath: str, page: int, idx: int) -> str:
        """Generates a stable unique chunk ID."""
        hash_base = f"{filepath}_{page}_{idx}"
        return hashlib.md5(hash_base.encode()).hexdigest()

    def _crop_element(
        self,
        pdf_doc: pdfium.PdfDocument,
        page_num: int,
        bbox: Any,
        page_width: float,
        page_height: float
    ) -> Optional[bytes]:
        """Crops a specific bounding box region from a PDF page and returns raw bytes."""
        try:
            # pdfium page indices are 0-indexed, docling is 1-indexed
            pdfium_page = pdf_doc[page_num - 1]
            # Render page at 150 DPI (approx scale 2)
            scale = 2.0
            pil_image = pdfium_page.render(scale=scale).to_pil()

            img_w, img_h = pil_image.size
            scale_x = img_w / page_width
            scale_y = img_h / page_height

            # Docling coordinates: origin bottom-left (Standard PDF coordinate space)
            # bbox has fields: l (left), b (bottom), r (right), t (top)
            # PIL origin: top-left
            l = getattr(bbox, "l", 0.0)
            b = getattr(bbox, "b", 0.0)
            r = getattr(bbox, "r", 0.0)
            t = getattr(bbox, "t", 0.0)

            x0 = int(l * scale_x)
            x1 = int(r * scale_x)
            
            # Map bottom-left Y coordinate system to top-left Y coordinate system
            y0 = int((page_height - t) * scale_y)
            y1 = int((page_height - b) * scale_y)

            # Ensure bounds are within image size
            x0 = max(0, min(x0, img_w))
            x1 = max(0, min(x1, img_w))
            y0 = max(0, min(y0, img_h))
            y1 = max(0, min(y1, img_h))

            if x1 <= x0 or y1 <= y0:
                return None

            cropped = pil_image.crop((x0, y0, x1, y1))
            buf = BytesIO()
            cropped.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.error("Failed to crop PDF element", error=str(e), page=page_num)
            return None

    async def extract(self, file_path: str) -> List[PerceptionChunk]:
        """Runs layout extraction on a PDF file, routing zones dynamically."""
        ctx_source_file.set(os.path.basename(file_path))
        ctx_modality.set("pdf")
        ctx_pipeline_stage.set("extraction")
        
        logger.info("Starting layout-guided PDF extraction", file=file_path)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        chunks: List[PerceptionChunk] = []

        try:
            # 1. Run Docling Layout Analysis
            result = self.converter.convert(file_path)
            doc = result.document

            # 2. Open PDF with pdfium for rendering figures/low confidence zones
            pdf_doc = pdfium.PdfDocument(file_path)

            idx = 0
            # 3. Iterate detected layout zones
            for element, level in doc.iterate_items():
                idx += 1
                class_name = element.__class__.__name__

                # Retrieve page information & dimensions
                prov = getattr(element, "prov", None)
                if not prov or not len(prov):
                    continue

                page_info = prov[0]
                page_num = page_info.page_no
                bbox = page_info.bbox

                # Find page dimensions
                # Docling page sizes are stored in points (72 DPI)
                page_size = doc.pages.get(page_num)
                page_width = page_size.size.width if page_size else 612.0
                page_height = page_size.size.height if page_size else 792.0

                chunk_id = self._generate_chunk_id(file_path, page_num, idx)

                # Initialize metadata
                meta = {
                    "layout_type": class_name,
                    "pii_detected": False,
                    "routing_decision": "none"
                }

                # --- 3.1: Table Zones ---
                if "Table" in class_name:
                    meta["routing_decision"] = "table_extract"
                    logger.info("PDF Extractor: Routing table zone", chunk_id=chunk_id, page=page_num)
                    
                    # Convert to markdown using Docling native methods
                    table_md = ""
                    if hasattr(element, "export_to_markdown"):
                        table_md = element.export_to_markdown()
                    else:
                        table_md = getattr(element, "text", "")

                    # Check PII
                    detected_pii = self.sensitivity_scanner.scan_for_pii(table_md)
                    if detected_pii:
                        meta["pii_detected"] = True
                        meta["pii_labels"] = detected_pii
                        table_md = self.sensitivity_scanner.redact_pii(table_md)

                    # Crop table image if possible to carry as base64 payload
                    crop_bytes = self._crop_element(pdf_doc, page_num, bbox, page_width, page_height)
                    content_b64 = base64.b64encode(crop_bytes).decode("utf-8") if crop_bytes else None

                    chunks.append(
                        PerceptionChunk(
                            chunk_id=chunk_id,
                            modality=ModalityType.PDF,
                            source_file=file_path,
                            page_number=page_num,
                            confidence=1.0,
                            content_text=table_md,
                            content_b64=content_b64,
                            structured_data={"markdown": table_md},
                            metadata=meta
                        )
                    )

                # --- 3.2: Figure / Picture Zones ---
                elif any(fig_lbl in class_name for fig_lbl in ["Picture", "Image", "Figure"]):
                    meta["routing_decision"] = "vlm_crop"
                    logger.info("PDF Extractor: Routing figure zone to cloud VLM crop", chunk_id=chunk_id, page=page_num)

                    # Crop figure from PDF page
                    crop_bytes = self._crop_element(pdf_doc, page_num, bbox, page_width, page_height)
                    
                    if crop_bytes:
                        content_b64 = base64.b64encode(crop_bytes).decode("utf-8")
                        # Call VLM on the surgical crop instead of the full page
                        prompt = "Describe this figure/diagram from a healthcare document in detail. What is its core message?"
                        try:
                            vlm_result = await self.vlm_client.analyze_image(prompt, image_bytes=crop_bytes)
                            desc = vlm_result.get("raw_text", "")
                            conf = 1.0
                        except Exception as e:
                            logger.error("VLM extraction on cropped figure failed", error=str(e))
                            desc = "Failed to analyze figure via VLM."
                            conf = 0.0
                    else:
                        content_b64 = None
                        desc = "No image bytes could be cropped for this figure."
                        conf = 0.0

                    chunks.append(
                        PerceptionChunk(
                            chunk_id=chunk_id,
                            modality=ModalityType.PDF,
                            source_file=file_path,
                            page_number=page_num,
                            confidence=conf,
                            content_text=desc,
                            content_b64=content_b64,
                            metadata=meta
                        )
                    )

                # --- 3.3: Text / Paragraph Zones ---
                else:
                    text_content = getattr(element, "text", "")
                    if not text_content.strip():
                        continue

                    # Determine Confidence - for standard text extraction, confidence is high.
                    # If it has a confidence score from layout engine (some packages have it), check it,
                    # otherwise default to 1.0 or confidence based on word counts.
                    zone_confidence = getattr(element, "confidence", 1.0)
                    
                    # Check PII
                    detected_pii = self.sensitivity_scanner.scan_for_pii(text_content)
                    if detected_pii:
                        meta["pii_detected"] = True
                        meta["pii_labels"] = detected_pii
                        text_content = self.sensitivity_scanner.redact_pii(text_content)

                    # Confidence routing decision
                    if zone_confidence >= config.high_confidence_threshold:
                        meta["routing_decision"] = "ocr_only"
                        logger.info("PDF Extractor: High confidence text chunk directly accepted", chunk_id=chunk_id, page=page_num, conf=zone_confidence)
                        chunks.append(
                            PerceptionChunk(
                                chunk_id=chunk_id,
                                modality=ModalityType.PDF,
                                source_file=file_path,
                                page_number=page_num,
                                confidence=zone_confidence,
                                content_text=text_content,
                                metadata=meta
                            )
                        )
                    else:
                        meta["routing_decision"] = "vlm_fallback_crop"
                        logger.info("PDF Extractor: Low confidence text chunk routed to VLM fallback", chunk_id=chunk_id, page=page_num, conf=zone_confidence)
                        
                        crop_bytes = self._crop_element(pdf_doc, page_num, bbox, page_width, page_height)
                        content_b64 = base64.b64encode(crop_bytes).decode("utf-8") if crop_bytes else None

                        if crop_bytes:
                            prompt = "Accurately transcribe the text in this image segment. Do not include markdown formatting or commentary."
                            try:
                                vlm_result = await self.vlm_client.analyze_image(prompt, image_bytes=crop_bytes)
                                text_content = vlm_result.get("raw_text", text_content)
                            except Exception as e:
                                logger.error("VLM text transcription fallback failed", error=str(e))
                                meta["vlm_fallback_failed"] = True

                        chunks.append(
                            PerceptionChunk(
                                chunk_id=chunk_id,
                                modality=ModalityType.PDF,
                                source_file=file_path,
                                page_number=page_num,
                                confidence=zone_confidence,
                                content_text=text_content,
                                content_b64=content_b64,
                                metadata=meta
                            )
                        )

            pdf_doc.close()
            logger.info("Completed layout-guided PDF extraction", total_chunks=len(chunks))
            return chunks

        except Exception as e:
            logger.error("Failed to parse PDF file", error=str(e))
            # Graceful wrapper: do not crash the orchestrator, log and flag
            return []
