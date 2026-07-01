"""Phase 1 - Configuration (Section 6.1: Perception Foundations).

All settings loaded from environment variables via pydantic-settings.
Copy .env.example to .env and fill in real values.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the multimodal perception pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    data_dir: Path = Path("./data")
    sample_data_dir: Path = Path("./data/samples")

    # Database (NeonDB / local Postgres)
    database_url: str = Field(
        default="postgresql+asyncpg://ch6user:ch6password@localhost:5432/ch6_perception"
    )

    # Qdrant vector store
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection_pdf: str = "ch6_pdf_chunks"
    qdrant_collection_image: str = "ch6_image_chunks"
    qdrant_collection_table: str = "ch6_table_chunks"
    qdrant_collection_audio: str = "ch6_audio_chunks"

    # Embedding models
    dense_embed_model: str = "jinaai/jina-embeddings-v3"
    dense_embed_dim: int = 1024
    sparse_embed_model: str = "naver/splade-cocondenser-ensemble-distil"

    # Vision-Language Model (Section 6.3)
    vlm_model: str = "HuggingFaceTB/SmolVLM-Instruct"
    vlm_max_new_tokens: int = 512

    # Named-Entity Recognition (Section 6.2)
    gliner_model: str = "urchade/gliner_medium-v2.1"

    # Whisper audio transcription (Section 6.4)
    whisper_model: str = "base"
    whisper_device: str = "cpu"

    # Optional OpenAI fallback
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Pipeline tuning (Section 6.5)
    chunk_size: int = 512
    chunk_overlap: int = 64
    retrieval_top_k: int = 5
    hybrid_alpha: float = Field(default=0.7, ge=0.0, le=1.0)
    max_concurrent_tasks: int = 4
    batch_size: int = 16

    @field_validator("data_dir", "sample_data_dir", mode="before")
    @classmethod
    def _to_path(cls, v: str | Path) -> Path:
        return Path(v)

    def ensure_dirs(self) -> None:
        """Create all required data subdirectories."""
        for sub in ("", "pdfs", "images", "tables", "audio", "samples"):
            (self.data_dir / sub).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton (safe to call anywhere)."""
    return Settings()
