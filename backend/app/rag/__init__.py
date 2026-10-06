"""RAG package."""
from .embedder import Embedder
from .index import EMBEDDINGS_FILE, PRODUCTS_FILE, RagIndex
from .retriever import ScoredProduct, cosine_search, similar_to_product

__all__ = [
    "Embedder",
    "RagIndex",
    "ScoredProduct",
    "cosine_search",
    "similar_to_product",
    "PRODUCTS_FILE",
    "EMBEDDINGS_FILE",
]
