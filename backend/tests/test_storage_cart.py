"""Unit tests — CartStore: tạo, token, thêm/sửa/xoá mục, TTL, persist JSONL."""
from __future__ import annotations

import pytest

from app.data.storage import CartStore
from helpers import make_product


@pytest.fixture
def products_index():
    p1 = make_product("P001", "áo", 450_000, stock={"S": 2, "M": 5, "L": 0})
    p2 = make_product("P002", "quần", 890_000, sizes=("M",), stock={"M": 3})
    return {p.id: p for p in (p1, p2)}


@pytest.fixture
async def store():
    return CartStore()


class TestCreateAndToken:
    async def test_create_returns_unique_cart_with_token(self, store):
        c1 = await store.create()
        c2 = await store.create()
        assert c1.cart_id != c2.cart_id
        assert c1.items == []
        assert len(c1.cart_token) >= 32

    async def test_verify_token_accepts_correct_rejects_wrong_or_unknown(self, store):
        cart = await store.create()
        assert await store.verify_token(cart.cart_id, cart.cart_token) is True
        assert await store.verify_token(cart.cart_id, "wrong-token") is False
        assert await store.verify_token("nonexistent", cart.cart_token) is False


class TestAddItem:
    async def test_add_snapshots_price_name_image(self, store, products_index):
        cart = await store.create()
        updated = await store.add_item(cart.cart_id, "P001", "M", 2, products_index)
        assert len(updated.items) == 1
        it = updated.items[0]
        assert (it.product_id, it.size, it.quantity) == ("P001", "M", 2)
        assert it.price_vnd_snapshot == 450_000
        assert it.name_snapshot == products_index["P001"].name

    async def test_add_same_product_size_merges_quantity(self, store, products_index):
        cart = await store.create()
        await store.add_item(cart.cart_id, "P001", "M", 1, products_index)
        updated = await store.add_item(cart.cart_id, "P001", "M", 2, products_index)
        assert len(updated.items) == 1
        assert updated.items[0].quantity == 3

    async def test_add_rejects_unknown_cart_product_size_and_zero_qty(self, store, products_index):
        cart = await store.create()
        with pytest.raises(ValueError, match="cart_not_found"):
            await store.add_item("ghost", "P001", "M", 1, products_index)
        with pytest.raises(ValueError, match="product_not_found"):
            await store.add_item(cart.cart_id, "PXXX", "M", 1, products_index)
        with pytest.raises(ValueError, match="size_unavailable"):
            await store.add_item(cart.cart_id, "P001", "XXL", 1, products_index)
        with pytest.raises(ValueError, match="invalid_quantity"):
            await store.add_item(cart.cart_id, "P001", "M", 0, products_index)


class TestUpdateRemoveClear:
    async def test_update_quantity_keeps_price_snapshot(self, store, products_index, monkeypatch):
        cart = await store.create()
        await store.add_item(cart.cart_id, "P001", "M", 1, products_index)
        # Catalog đổi giá SAU khi thêm — snapshot trong giỏ phải giữ nguyên.
        products_index["P001"] = make_product("P001", "áo", 999_000, stock={"M": 5})
        updated = await store.update_quantity(cart.cart_id, "P001", "M", 4)
        assert updated.items[0].quantity == 4
        assert updated.items[0].price_vnd_snapshot == 450_000


class TestTtlAndPersistence:
    async def test_cart_survives_restart_via_jsonl(self, products_index):
        store = CartStore()
        cart = await store.create()
        await store.add_item(cart.cart_id, "P001", "M", 2, products_index)
        reloaded = CartStore()
        got = await reloaded.get(cart.cart_id)
        assert got is not None
        assert got.items[0].quantity == 2
        assert got.cart_token == cart.cart_token

