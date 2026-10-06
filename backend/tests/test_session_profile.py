"""Unit tests — CustomerProfileStore (upsert/normalize/TTL) và SessionStore (TTL, stats)."""
from __future__ import annotations

from datetime import timedelta
from app.data.storage import CustomerProfileStore, _now
from app.session import SessionStore
from helpers import make_product


class TestCustomerProfileStore:
    async def test_upsert_normalizes_phone_key(self):
        ps = CustomerProfileStore()
        prof = await ps.upsert("  0900123456  ", "A", "addr")
        assert prof.phone == "0900123456"
        assert await ps.get("0900123456") is not None

    async def test_upsert_twice_updates_fields_keeps_created_at(self):
        ps = CustomerProfileStore()
        first = await ps.upsert("0900123456", "A", "old")
        second = await ps.upsert("0900123456", "B", "new")
        assert second.name == "B"
        assert second.address == "new"
        assert second.created_at == first.created_at
        assert second.last_seen_at >= first.last_seen_at

    async def test_sweep_expired_ttl_90_days(self):
        ps = CustomerProfileStore()
        old = await ps.upsert("0900000001", "Old", "a")
        fresh = await ps.upsert("0900000002", "Fresh", "b")
        ps._profiles[old.phone].last_seen_at = _now() - timedelta(days=91)
        swept = await ps.sweep_expired(ttl_seconds=90 * 86400)
        assert swept == 1
        assert await ps.get(old.phone) is None
        assert await ps.get(fresh.phone) is not None


class TestSessionStore:
    async def test_get_or_create_counts_customers_once(self):
        store = SessionStore()
        await store.get_or_create("s1")
        await store.get_or_create("s1")
        assert await store.total_customers() == 1

    async def test_track_tool_call_feeds_top_products(self):
        store = SessionStore()
        p1, p2 = make_product("P001"), make_product("P002")
        await store.track_tool_call("s1", "search_products", {}, [p1, p2])
        await store.track_tool_call("s1", "search_products", {}, [p1])
        top = await store.top_products(k=5)
        assert top[0] == {"id": "P001", "count": 2}
        assert {"id": "P002", "count": 1} in top

