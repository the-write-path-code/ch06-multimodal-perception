# Section 6.4: Embedding Package Exports

from ch6.embedding.dense import DenseEncoder
from ch6.embedding.sparse import SparseEncoder

__all__ = [
    "DenseEncoder",
    "SparseEncoder",
]
