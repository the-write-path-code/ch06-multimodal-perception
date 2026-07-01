# Section 6.4: Sparse Encoder

from typing import List, Dict, Any, Optional
from ch6.config import config
from ch6.logging import logger

class SparseEncoder:
    """Computes sparse term expansion vectors using FastEmbed (default model: Qdrant/bm42-all-minilm-l6-v2)."""

    def __init__(self) -> None:
        self._model = None

    def _load_model(self):
        """Lazily loads the FastEmbed sparse model."""
        if not config.enable_sparse_embeddings:
            return
        if self._model is not None:
            return

        try:
            from fastembed import SparseTextEmbedding
            # Splade_PP_en_v1 is a high-quality learned sparse model
            self._model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")
            logger.info("FastEmbed sparse model loaded successfully.")
        except Exception as e:
            logger.error("Failed to load sparse embedding model", error=str(e))
            raise e

    def embed_text(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Computes sparse vectors for list of text inputs.

        Returns a list of dictionaries structured as {'indices': List[int], 'values': List[float]}
        suitable for direct Qdrant sparse point upserts.
        """
        if not config.enable_sparse_embeddings:
            return [{"indices": [], "values": []} for _ in texts]

        self._load_model()
        if not self._model:
            raise RuntimeError("Sparse model not initialized")

        try:
            embeddings = list(self._model.embed(texts))
            results = []
            for emb in embeddings:
                results.append({
                    "indices": emb.indices.tolist(),
                    "values": emb.values.tolist()
                })
            return results
        except Exception as e:
            logger.error("Sparse embedding computation failed", error=str(e))
            # Safe wrapper: return empty sparse vectors on failure
            return [{"indices": [], "values": []} for _ in texts]
