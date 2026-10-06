"""Unit tests — tool handlers: payload cho LLM + products render, lỗi nghiệp vụ trả {"error": ...}."""
from __future__ import annotations

import pytest

from app.data.storage import CartStore, CustomerProfileStore, OrderStore
from app.tools import DISPATCH, list_tool_names
from app.tools.handlers import ToolContext, handle_add_to_cart, handle_check_stock, handle_create_order, handle_get_cart, handle_get_product, handle_recommend_similar, handle_search_products, handle_update_customer_profile
from helpers import make_index, make_product


class FakeEmbedder:
    """Embed deterministically: query chứa 'quần' → hướng quần, ngược lại hướng áo."""

    backend = "fake"

    async def embed(self, texts):
        return [[1.0, 0.0, 0.0] if "quần" not in t else [0.0, 1.0, 0.0] for t in texts]


@pytest.fixture
def products():
    return [
        make_product("P001", "áo", 450_000, colors=("đen",), stock={"M": 5}),
        make_product("P002", "áo", 600_000, colors=("trắng",), stock={"M": 1}),
        make_product("P003", "quần", 890_000, stock={"M": 0}),
        make_product("P004", "váy", 1_200_000, stock={"S": 3}),
    ]


@pytest.fixture
def ctx(products):
    index = make_index(
        products,
        [[1, 0, 0], [0.9, 0.1, 0], [0, 1, 0], [0, 0, 1]],
    )
    return ToolContext(
        index=index,
        embedder=FakeEmbedder(),
        cart_store=CartStore(),
        order_store=OrderStore(),
        profile_store=CustomerProfileStore(),
        products_index={p.id: p for p in products},
        cart_id=None,
        cart_token=None,
    )


async def with_cart(ctx):
    cart = await ctx.cart_store.create()
    ctx.cart_id = cart.cart_id
    ctx.cart_token = cart.cart_token
    return cart


class TestDispatchSurface:
    def test_dispatch_matches_schema_names(self):
        from app.tools.schemas import CUSTOMER_TOOLS

        schema_names = {t["function"]["name"] for t in CUSTOMER_TOOLS}
        assert set(list_tool_names()) == schema_names
        assert set(DISPATCH) == schema_names


class TestSearchProducts:
    async def test_returns_sorted_products_and_payload(self, ctx):
        tr = await handle_search_products({"query": "áo sơ mi"}, ctx)
        # không có filter cứng → trả top_k=5 theo cosine: P001 (1.0), P002 (0.9), còn lại ~0
        ids = [p.id for p in tr.products]
        assert ids[:2] == ["P001", "P002"]
        assert tr.llm_payload["found"] == len(ids)
        scores = [p["score"] for p in tr.llm_payload["products"]]
        assert scores == sorted(scores, reverse=True)


class TestGetProductAndStock:
    async def test_get_product_found(self, ctx):
        tr = await handle_get_product({"product_id": "P001"}, ctx)
        assert tr.llm_payload["id"] == "P001"
        assert tr.llm_payload["price_vnd"] == 450_000
        assert tr.products == [ctx.index.products[0]]


    async def test_check_stock_by_size(self, ctx):
        tr = await handle_check_stock({"product_id": "P001", "size": "M"}, ctx)
        assert tr.llm_payload["in_stock"] is True
        assert tr.llm_payload["quantity"] == 5


class TestCartTools:
    async def test_add_to_cart_success_and_get_cart(self, ctx):
        await with_cart(ctx)
        tr = await handle_add_to_cart({"product_id": "P001", "size": "M", "quantity": 2}, ctx)
        assert "error" not in tr.llm_payload
        assert len(tr.llm_payload["items"]) == 1
        assert tr.llm_payload["items"][0]["price_vnd_snapshot"] == 450_000
        assert tr.products[0].id == "P001"

        tr2 = await handle_get_cart({}, ctx)
        assert tr2.llm_payload["items"][0]["quantity"] == 2

    async def test_add_to_cart_out_of_stock_error_to_llm(self, ctx):
        """Lỗi nghiệp vụ phải về LLM dạng JSON, không exception."""
        await with_cart(ctx)
        tr = await handle_add_to_cart({"product_id": "P003", "size": "M", "quantity": 1}, ctx)
        assert "out_of_stock" in tr.llm_payload["error"]



class TestRecommendSimilar:
    async def test_similar_mode_same_category_excludes_cart(self, ctx):
        await with_cart(ctx)
        await handle_add_to_cart({"product_id": "P001", "size": "M", "quantity": 1}, ctx)
        tr = await handle_recommend_similar({"mode": "similar", "k": 3}, ctx)
        assert tr.llm_payload["mode"] == "similar"
        ids = [p["id"] for p in tr.llm_payload["similar"]]
        assert ids == ["P002"]  # chỉ P002 cùng category 'áo', P001 bị loại vì ở trong giỏ

    async def test_complement_mode_uses_map(self, ctx):
        """Giỏ có váy (P004) → complement map váy→[áo, phụ kiện, giày] → trả về áo."""
        await with_cart(ctx)
        await handle_add_to_cart({"product_id": "P004", "size": "S", "quantity": 1}, ctx)
        tr = await handle_recommend_similar({"mode": "complement", "k": 3}, ctx)
        assert tr.llm_payload["mode"] == "complement"
        ids = {p["id"] for p in tr.llm_payload["complement"]}
        assert ids == {"P001", "P002"}
        assert all(p["category"] == "áo" for p in tr.llm_payload["complement"])


class TestProfileAndOrder:
    async def test_happy_flow_profile_then_order(self, ctx):
        await with_cart(ctx)
        await handle_add_to_cart({"product_id": "P001", "size": "M", "quantity": 2}, ctx)
        prof = await handle_update_customer_profile(
            {"phone": "0900123456", "name": "A", "address": "1 Lê Lợi"}, ctx
        )
        assert prof.llm_payload["phone"] == "0900123456"

        tr = await handle_create_order({"phone": "0900123456"}, ctx)
        order = tr.llm_payload
        assert "error" not in order
        assert order["status"] == "pending"
        assert order["total_vnd"] == 900_000
        assert order["customer_name"] == "A"
        assert tr.products[0].id == "P001"

        # Đơn đã tạo — giỏ vẫn còn (chưa clear) nhưng store có order
        stored = await ctx.order_store.get(order["order_id"])
        assert stored is not None
