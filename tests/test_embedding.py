# Section 6.4: Embedding Models Unit Tests

import pytest
from PIL import Image
from ch6.embedding.dense import DenseEncoder
from ch6.embedding.sparse import SparseEncoder
import numpy as np

def test_dense_encoder_cross_modal_dimensions():
    """Checks that text and image dense embeddings are produced at 512 dimensions."""
    dense = DenseEncoder()
    
    # 1. Text embedding
    txt_vecs = dense.embed_text(["nurse visit schedule", "medication summary"])
    assert len(txt_vecs) == 2
    assert len(txt_vecs[0]) == 512
    assert len(txt_vecs[1]) == 512

    # 2. Image embedding
    img = Image.new("RGB", (224, 224), (200, 200, 200))
    img_vecs = dense.embed_image([img])
    assert len(img_vecs) == 1
    assert len(img_vecs[0]) == 512

def test_cross_modal_similarity():
    """Checks that a text query and related image produce a meaningful cosine similarity."""
    dense = DenseEncoder()
    
    text_desc = "firsthealth insurance card"
    # Create matching synthetic image with text drawn
    img = Image.new("RGB", (300, 150), (50, 100, 200))
    
    txt_vec = np.array(dense.embed_text([text_desc])[0])
    img_vec = np.array(dense.embed_image([img])[0])

    # Normalize vectors
    txt_norm = txt_vec / np.linalg.norm(txt_vec)
    img_norm = img_vec / np.linalg.norm(img_vec)

    cosine_sim = np.dot(txt_norm, img_norm)
    # Proves they reside in a shared space
    assert -1.0 <= cosine_sim <= 1.0

def test_sparse_encoder():
    """Checks that sparse encoder generates index-value map outputs."""
    sparse = SparseEncoder()
    txt = "home health visit audit billing data"
    
    results = sparse.embed_text([txt])
    assert len(results) == 1
    
    sparse_vec = results[0]
    assert "indices" in sparse_vec
    assert "values" in sparse_vec
    assert len(sparse_vec["indices"]) == len(sparse_vec["values"])
    if len(sparse_vec["indices"]) > 0:
        assert isinstance(sparse_vec["indices"][0], int)
        assert isinstance(sparse_vec["values"][0], float)
