# Section 6.2: Perception Dispatcher

import os
import mimetypes
from typing import List
from ch6.logging import logger
from ch6.models import PerceptionChunk
from ch6.perception.pdf import PDFExtractor
from ch6.perception.image import ImageExtractor
from ch6.perception.table import TableExtractor
from ch6.perception.audio import AudioExtractor

class PerceptionDispatcher:
    """Detects file modality and coordinates routing to the correct extraction engine."""

    def __init__(self) -> None:
        self.pdf_extractor = PDFExtractor()
        self.image_extractor = ImageExtractor()
        self.table_extractor = TableExtractor()
        self.audio_extractor = AudioExtractor()

    async def perceive(self, file_path: str) -> List[PerceptionChunk]:
        """Routes a file to the appropriate modality extractor based on mime-type / extension.

        Ensures that errors on individual files are caught gracefully, logging the failure
        and returning an empty list instead of raising an unhandled exception.
        """
        if not os.path.exists(file_path):
            logger.error("File does not exist", path=file_path)
            return []

        _, ext = os.path.splitext(file_path.lower())
        
        # Mime type check as secondary safety
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or ""

        try:
            # Route based on extension/mime-type
            if ext == ".pdf" or "pdf" in mime_type:
                logger.info("Dispatcher: Routing file to PDF Extractor", file=file_path)
                return await self.pdf_extractor.extract(file_path)

            elif ext in [".png", ".jpg", ".jpeg", ".webp"] or "image" in mime_type:
                logger.info("Dispatcher: Routing file to Image Extractor", file=file_path)
                return await self.image_extractor.extract(file_path)

            elif ext in [".csv", ".xlsx", ".xls"] or "csv" in mime_type or "spreadsheet" in mime_type or "excel" in mime_type:
                logger.info("Dispatcher: Routing file to Tabular Extractor", file=file_path)
                return await self.table_extractor.extract(file_path)

            elif ext in [".wav", ".mp3", ".m4a"] or "audio" in mime_type or "wav" in mime_type:
                logger.info("Dispatcher: Routing file to Audio Extractor", file=file_path)
                return await self.audio_extractor.extract(file_path)

            else:
                logger.warning("Dispatcher: Unknown file type or modality. Ignoring file.", file=file_path, extension=ext)
                return []

        except Exception as e:
            logger.error("Dispatcher encountered error during file perception", file=file_path, error=str(e))
            # Catch-all to make sure one bad file never halts the pipeline
            return []
