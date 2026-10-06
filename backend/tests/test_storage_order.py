"""Unit tests — OrderStore: snapshot từ giỏ, transition table, tra cứu, price mismatch."""
from __future__ import annotations

import pytest

from app.data.storage import CartStore, CustomerProfileStore, OrderStore
from helpers import make_product


@pytest.fixture
def products_index():
    p1 = make_product("P001", "áo", 450_000)
    p2 = make_product("P002", "quần", 890_000)
    return {p.id: p for p in (p1, p2)}


@pytest.fixture
async def profile():
    ps = CustomerProfileStore()
    return await ps.upsert(" 0900123456 ", "Nguyễn Văn A", "1 Lê Lợi, Q1")


async def filled_cart(products_index, items):
    cs = CartStore()
    cart = await cs.create()
    for pid, size, qty in items:
        await cs.add_item(cart.cart_id, pid, size, qty, products_index)
    return cart


class TestCreateFromCart:
    async def test_order_snapshots_items_and_total(self, products_index, profile):
        cart = await filled_cart(products_index, [("P001", "M", 2), ("P002", "L", 1)])
        order = await OrderStore().create_from_cart(cart, profile)
        assert order.status == "pending"
        assert order.total_vnd == 450_000 * 2 + 890_000
        assert len(order.items) == 2
        assert order.items[0].name_snapshot.startswith("Sản phẩm P001")
        assert order.status_history[0]["status"] == "pending"
        # phone đã normalize khi upsert
        assert order.customer_phone == "0900123456"

    async def test_order_items_are_copies_not_references(self, products_index, profile):
        cart = await filled_cart(products_index, [("P001", "M", 1)])
        store = OrderStore()
        order = await store.create_from_cart(cart, profile)
        cart.items.pop(0)
        got = await store.get(order.order_id)
        assert len(got.items) == 1


class TestTransitions:
    async def make_order(self, products_index, profile):
        cart = await filled_cart(products_index, [("P001", "M", 1)])
        store = OrderStore()
        order = await store.create_from_cart(cart, profile)
        return store, order.order_id

    async def test_full_happy_path(self, products_index, profile):
        store, oid = await self.make_order(products_index, profile)
        for status in ("confirmed", "shipped", "completed"):
            order = await store.transition(oid, status)
            assert order.status == status
        final = await store.get(oid)
        assert [h["status"] for h in final.status_history] == [
            "pending",
            "confirmed",
            "shipped",
            "completed",
        ]


class TestQueries:
    async def test_list_by_phone_strips_whitespace(self, products_index, profile):
        cart = await filled_cart(products_index, [("P001", "M", 1)])
        store = OrderStore()
        await store.create_from_cart(cart, profile)
        assert len(await store.list_by_phone("  0900123456  ")) == 1
        assert await store.list_by_phone("0900000000") == []

    async def test_price_mismatch_only_returns_open_orders_with_newer_price(self, products_index, profile):
        cart = await filled_cart(products_index, [("P001", "M", 1)])
        store = OrderStore()
        order = await store.create_from_cart(cart, profile)

        # Giá catalog đổi: 450k → 500k
        changed = {**products_index, "P001": make_product("P001", "áo", 500_000)}
        mismatched = await store.list_all(price_mismatch_only=True, products_index=changed)
        assert [o.order_id for o in mismatched] == [order.order_id]

        # Không đổi giá → không có mismatch
        assert await store.list_all(price_mismatch_only=True, products_index=products_index) == []

    async def test_orders_persist_across_restart(self, products_index, profile):
        cart = await filled_cart(products_index, [("P001", "M", 1)])
        store = OrderStore()
        order = await store.create_from_cart(cart, profile)
        reloaded = OrderStore()
        got = await reloaded.get(order.order_id)
        assert got is not None
        assert got.total_vnd == order.total_vnd
