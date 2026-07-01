# Section 6.4: Unified Retrieval Service

from typing import List, Dict, Any, Optional
from PIL import Image
from ch6.logging import logger
from ch6.retrieval.registry import AssetRegistry
from ch6.retrieval.store import VectorCatalog

class SearchService:
    """Combines vector catalog similarities with localized database records to retrieve enriched chunks."""

    def __init__(self) -> None:
        self.catalog = VectorCatalog()
        self.registry = AssetRegistry()

    async def search(
        self,
        text_query: Optional[str] = None,
        image_query: Optional[Image.Image] = None,
        top_k: int = 5,
        filter_modality: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Queries the vector catalog and enriches point results with complete details from the SQLite registry."""
        # 1. Fetch similarities from Qdrant
        logger.info(
            "Executing unified search",
            has_text=text_query is not None,
            has_image=image_query is not None,
            filter_modality=filter_modality
        )
        
        matches = await self.catalog.search(
            text_query=text_query,
            image_query=image_query,
            top_k=top_k,
            filter_modality=filter_modality
        )

        results = []
        for match in matches:
            pt_id = match["qdrant_point_id"]
            score = match["score"]
            payload = match["payload"]

            # 2. Query registry database for complete record details
            db_chunk = await self.registry.get_chunk_by_qdrant_id(pt_id)
            if db_chunk:
                results.append({
                    "qdrant_point_id": pt_id,
                    "score": score,
                    "modality": db_chunk["modality"],
                    "page_number": db_chunk["page_number"],
                    "source_file": payload.get("source_file"),
                    "content_preview": db_chunk["content_preview"],
                    "metadata": db_chunk["metadata"],
                    "structured_data": db_chunk["structured_data"]
                })
            else:
                # Fallback to payload details if registry record is not found (e.g. deleted from SQLite but not Qdrant)
                results.append({
                    "qdrant_point_id": pt_id,
                    "score": score,
                    "modality": payload.get("modality"),
                    "page_number": payload.get("page_number"),
                    "source_file": payload.get("source_file"),
                    "content_preview": payload.get("content_text", "")[:200],
                    "metadata": payload.get("metadata", {}),
                    "structured_data": payload.get("structured_data")
                })

        return results
