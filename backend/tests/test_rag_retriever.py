"""Unit tests — cosine_search (bộ lọc cứng) và similar_to_product."""
from __future__ import annotations

from app.rag.retriever import cosine_search, similar_to_product
from helpers import make_index, make_product


class TestCosineSearch:
    def test_ranks_by_cosine_desc(self, rag_index):
        hits = cosine_search(rag_index, [1.0, 0.0, 0.0], top_k=3)
        assert [h.product.id for h in hits] == ["P001", "P002", "P003"]
        assert hits[0].score > hits[1].score > hits[2].score

    def test_category_filter(self, rag_index):
        hits = cosine_search(rag_index, [1.0, 0.0, 0.0], category="quần")
        assert [h.product.id for h in hits] == ["P002"]

    def test_combined_filters(self, rag_index):
        hits = cosine_search(
            rag_index, [1.0, 0.0, 0.0], category="áo", max_price=500_000, size="M", color="đen"
        )
        assert [h.product.id for h in hits] == ["P001"]

class TestSimilarToProduct:
    def test_same_category_only_excludes_self(self):
        products = [
            make_product("P001", "áo"),
            make_product("P002", "áo"),
            make_product("P003", "quần"),
        ]
        idx = make_index(products, [[1.0, 0.0], [0.9, 0.1], [0.95, 0.05]])
        hits = similar_to_product(idx, "P001", k=3)
        # P003 gần hơn nhưng khác category → bị loại
        assert [h.product.id for h in hits] == ["P002"]

