# Section 6.2: Orchestration Config

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    def __init__(self, *args, **kwargs):
        if "PYTEST_CURRENT_TEST" in os.environ and "_env_file" not in kwargs:
            kwargs["_env_file"] = None
        super().__init__(*args, **kwargs)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Orchestration and Concurrency
    pipeline_concurrency: int = Field(default=5, description="Concurrency limit for processing files in parallel")
    sample_data_dir: str = Field(default="data/samples", description="Directory where sample data is stored or generated")
    registry_db_path: str = Field(default="data/registry.db", description="Path to the SQLite asset registry database")

    # Modality Extractors Configs
    whisper_model_size: str = Field(default="base", description="Local faster-whisper model size to load")
    high_confidence_threshold: float = Field(default=0.85, description="Threshold above which direct OCR is trusted")
    low_confidence_threshold: float = Field(default=0.50, description="Threshold below which human review is flagged")
    vlm_crop_strategy: str = Field(default="zone_crop", description="VLM calling crop strategy: full_page, zone_crop, or band_crop")

    # Embeddings config
    enable_sparse_embeddings: bool = Field(default=True, description="Whether to compute SPLADE sparse vectors")
    dense_embedding_model: str = Field(default="clip-ViT-B-32", description="HuggingFace model ID for dense cross-modal embeddings")

    # Cloud VLM config (Gemini or NVIDIA NIM)
    gemini_api_key: Optional[str] = Field(default=None, description="API Key for Google Gemini Cloud VLM")
    nvidia_api_key: Optional[str] = Field(default=None, description="API Key for NVIDIA NIM API Catalog")
    nvidia_vlm_model: str = Field(default="meta/llama-3.2-11b-vision-instruct", description="VLM model identifier from NVIDIA API Catalog")

    # Local VLM config (Ollama)
    use_local_vlm: bool = Field(default=False, description="Flag to force fallback to local Ollama VLM")
    local_vlm_model: str = Field(default="llava", description="Ollama model name to use for local fallback VLM")
    ollama_host: str = Field(default="http://localhost:11434", description="Ollama API base host URL")

    # Vector Database (Qdrant)
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant API instance endpoint URL")
    qdrant_api_key: Optional[str] = Field(default=None, description="Qdrant auth token / API key")
    qdrant_collection: str = Field(default="multimodal_perception", description="Qdrant vector collection name")

    # Hugging Face (Optional)
    hf_token: Optional[str] = Field(default=None, description="Hugging Face access token for protected models")

# Instantiated config singleton
config = AppConfig()
