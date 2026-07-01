# Section 6.5: End-to-End Pipeline Execution

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load env variables from .env file
load_dotenv()

from ch6.config import config
from ch6.logging import logger
from ch6.pipeline import PerceptionPipeline
from ch6.query import SearchService

async def main():
    logger.info("Starting live pipeline execution with Google Gemini VLM...", qdrant_url=config.qdrant_url)

    # 1. Initialize Pipeline
    pipeline = PerceptionPipeline()
    await pipeline.initialize()

    # 2. Collect sample files
    sample_dir = Path("data/samples")
    files_to_process = [
        sample_dir / "patient_care_protocol.pdf",
        sample_dir / "insurance_card_front.png",
        sample_dir / "audit_report.csv",
        sample_dir / "nurse_visit_note_001.wav"
    ]

    all_handoffs = []

    # 3. Process files through pipeline
    for file_path in files_to_process:
        if not file_path.exists():
            logger.warn("Sample file not found, skipping", path=str(file_path))
            continue

        logger.info(f"Ingesting file: {file_path.name}")
        try:
            handoffs = await pipeline.ingest_document(str(file_path))
            all_handoffs.extend(handoffs)
            for h in handoffs:
                logger.info(
                    "Processed chunk",
                    chunk_id=h.chunk.chunk_id,
                    modality=h.chunk.modality.value,
                    status=h.validation_status,
                    flags=h.flags,
                    preview=h.chunk.content_text[:80].replace('\n', ' ')
                )
        except Exception as e:
            logger.error("Failed to ingest file", path=str(file_path), error=str(e))

    logger.info("Ingestion completed.", total_chunks=len(all_handoffs))

    # 4. Search Queries
    search_service = SearchService()
    
    # Query 1: Text search with higher top_k
    query_text = "What is the copay amount on the insurance card?"
    logger.info("Executing text search query", query=query_text)
    text_results = await search_service.search(text_query=query_text, top_k=5)
    for idx, r in enumerate(text_results):
        logger.info(
            f"Text Search Result #{idx+1}",
            score=r["score"],
            source=r["source_file"],
            preview=r["content_preview"][:120].replace('\n', ' '),
            structured=r["structured_data"]
        )

    # Query 2: Audio/Text cross-modal search
    query_text2 = "John Smith patient checkup visit"
    logger.info("Executing cross-modal query", query=query_text2)
    audio_results = await search_service.search(text_query=query_text2, filter_modality="audio", top_k=2)
    for idx, r in enumerate(audio_results):
        logger.info(
            f"Audio Search Result #{idx+1}",
            score=r["score"],
            source=r["source_file"],
            preview=r["content_preview"][:120].replace('\n', ' '),
            structured=r["structured_data"]
        )

    # Query 3: Image-filtered text search
    query_text3 = "Member ID HFP-98765432-01"
    logger.info("Executing image-filtered text search", query=query_text3)
    image_filtered_results = await search_service.search(text_query=query_text3, filter_modality="image", top_k=2)
    for idx, r in enumerate(image_filtered_results):
        logger.info(
            f"Image-Filtered Search Result #{idx+1}",
            score=r["score"],
            source=r["source_file"],
            preview=r["content_preview"][:120].replace('\n', ' '),
            structured=r["structured_data"]
        )

    # Query 4: Visual image-to-image search
    from PIL import Image as PILImage
    card_img_path = "data/samples/insurance_card_front.png"
    if os.path.exists(card_img_path):
        logger.info("Executing visual image search using card crop", path=card_img_path)
        img_obj = PILImage.open(card_img_path)
        visual_results = await search_service.search(image_query=img_obj, top_k=2)
        for idx, r in enumerate(visual_results):
            logger.info(
                f"Visual Search Result #{idx+1}",
                score=r["score"],
                source=r["source_file"],
                preview=r["content_preview"][:120].replace('\n', ' '),
                structured=r["structured_data"]
            )

if __name__ == "__main__":
    asyncio.run(main())
