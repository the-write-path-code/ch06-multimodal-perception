# Section 6.2: Asset Database Registry

import os
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
import aiosqlite

from ch6.config import config
from ch6.logging import logger

class AssetRegistry:
    """Async database registry tracking ingested documents and chunks locally in SQLite."""

    def __init__(self) -> None:
        self.db_path = config.registry_db_path
        # Ensure parent folder exists
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

    async def initialize(self) -> None:
        """Initializes tables for document and chunk storage if they do not exist."""
        logger.info("Initializing asset registry database", path=self.db_path)
        async with aiosqlite.connect(self.db_path) as db:
            # Create documents table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filepath TEXT UNIQUE,
                    modality TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            """)

            # Create chunks table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    modality TEXT NOT NULL,
                    page_number INTEGER,
                    qdrant_point_id TEXT,
                    content_preview TEXT,
                    metadata_json TEXT,
                    structured_data_json TEXT,
                    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
                )
            """)
            await db.commit()

    async def register_document(self, doc_id: str, filepath: str, modality: str) -> str:
        """Registers or updates a document metadata record. Returns the document ID."""
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO documents (id, filepath, modality, processed_at, status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(filepath) DO UPDATE SET
                    processed_at = excluded.processed_at,
                    status = excluded.status
            """, (doc_id, filepath, modality, now, "PROCESSED"))
            await db.commit()
        return doc_id

    async def register_chunk(
        self,
        doc_id: str,
        chunk_id: str,
        modality: str,
        page_number: Optional[int],
        qdrant_point_id: Optional[str],
        content_preview: str,
        metadata: Dict[str, Any],
        structured_data: Optional[Dict[str, Any]]
    ) -> None:
        """Registers a chunk record associated with a registered document."""
        meta_json = json.dumps(metadata)
        struct_json = json.dumps(structured_data) if structured_data else None

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO chunks (id, document_id, modality, page_number, qdrant_point_id, content_preview, metadata_json, structured_data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (chunk_id, doc_id, modality, page_number, qdrant_point_id, content_preview, meta_json, struct_json))
            await db.commit()

    async def get_chunk_by_qdrant_id(self, qdrant_point_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves raw chunk details from SQLite using the vector database point ID reference."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            async with db.execute(
                "SELECT * FROM chunks WHERE qdrant_point_id = ?",
                (qdrant_point_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                
                return {
                    "id": row["id"],
                    "document_id": row["document_id"],
                    "modality": row["modality"],
                    "page_number": row["page_number"],
                    "qdrant_point_id": row["qdrant_point_id"],
                    "content_preview": row["content_preview"],
                    "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else {},
                    "structured_data": json.loads(row["structured_data_json"]) if row["structured_data_json"] else None
                }
