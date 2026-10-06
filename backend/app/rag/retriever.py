"""Cosine similarity + filter cứng trên RAG index."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from ..schemas import Product
from .index import RagIndex


@dataclass
class ScoredProduct:
    product: Product
    score: float


def cosine_search(
    index: RagIndex,
    query_vec: List[float],
    top_k: int = 5,
    category: Optional[str] = None,
    max_price: Optional[int] = None,
    size: Optional[str] = None,
    gender: Optional[str] = None,
    color: Optional[str] = None,
) -> List[ScoredProduct]:
    """Tìm top_k sản phẩm có cosine cao nhất sau khi áp filter cứng."""
    if not index.products:
        return []

    q = np.asarray(query_vec, dtype=np.float32).reshape(1, -1)
    # cosine = (A · B) / (||A|| * ||B||)
    a_norm = np.linalg.norm(index.embeddings, axis=1, keepdims=True)
    a_norm = np.where(a_norm == 0, 1e-9, a_norm)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return []
    sims = (index.embeddings @ q.T).flatten() / (a_norm.flatten() * q_norm)

    candidates: List[ScoredProduct] = []
    for i, p in enumerate(index.products):
        if category and p.category != category:
            continue
        if max_price is not None and p.price_vnd > max_price:
            continue
        if size and size not in p.sizes_available:
            continue
        if gender and p.gender not in (gender, "unisex"):
            continue
        if color:
            colors_lower = {c.lower() for c in p.colors}
            if color.lower() not in colors_lower:
                continue
        candidates.append(ScoredProduct(product=p, score=float(sims[i])))

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:top_k]


def similar_to_product(
    index: RagIndex,
    product_id: str,
    k: int = 3,
) -> List[ScoredProduct]:
    """Sản phẩm tương tự (dựa trên vector, cùng category)."""
    if product_id not in index.by_id:
        return []
    base = index.products[index.by_id[product_id]]
    base_vec = index.embeddings[index.by_id[product_id]]
    sims = index.embeddings @ base_vec / (
        np.linalg.norm(index.embeddings, axis=1) * np.linalg.norm(base_vec) + 1e-9
    )
    out: List[ScoredProduct] = []
    for i, p in enumerate(index.products):
        if p.id == product_id:
            continue
        if p.category != base.category:
            continue
        out.append(ScoredProduct(product=p, score=float(sims[i])))
    out.sort(key=lambda c: c.score, reverse=True)
    return out[:k]
