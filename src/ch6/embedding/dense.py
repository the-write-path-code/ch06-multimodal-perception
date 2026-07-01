# Section 6.4: Dense Encoder

import os
from typing import List, Union
from PIL import Image
from ch6.config import config
from ch6.logging import logger

class DenseEncoder:
    """Wraps SentenceTransformer CLIP model to map text and images to a shared vector space."""

    def __init__(self) -> None:
        self._model = None

    def _load_model(self):
        """Lazily loads the SentenceTransformer model."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
            # clip-ViT-B-32 maps images and text to 512-dimension space
            self._model = SentenceTransformer(config.dense_embedding_model)
            logger.info("SentenceTransformer dense model loaded successfully.", model=config.dense_embedding_model)
        except Exception as e:
            logger.error("Failed to load dense embedding model", error=str(e))
            raise e

    def embed_text(self, texts: List[str]) -> List[List[float]]:
        """Computes dense embeddings for list of text inputs."""
        self._load_model()
        if not self._model:
            raise RuntimeError("Model not initialized")
        
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [vec.tolist() for vec in embeddings]

    def embed_image(self, images: List[Image.Image]) -> List[List[float]]:
        """Computes dense embeddings for list of PIL Image inputs."""
        self._load_model()
        if not self._model:
            raise RuntimeError("Model not initialized")

        embeddings = self._model.encode(images, convert_to_numpy=True)
        return [vec.tolist() for vec in embeddings]
