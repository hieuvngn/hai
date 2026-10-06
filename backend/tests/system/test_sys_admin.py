"""TC-ADM — quản trị trên server thật (mục 5.4.4 báo cáo).

CRUD được thực hiện trên sandbox state riêng; các bài sinh viên chạy theo thứ tự
 alphabetical nên viết lại luôn idempotent theo vị test của mình.
"""
from __future__ import annotations


import pytest

pytestmark = pytest.mark.system


class TestAdminAuthAndStats:
    def test_tc_adm_01_login_wrong_token_rejected(self, live):
        r = live.c.post("/api/admin/login", json={"token": "sai-quay-gi-do"})
        assert r.status_code == 401
        # endpoint protected vẫn đóng với người chưa xác thực
        assert live.a("get", "/stats", headers={"Authorization": "Bearer sai"}).status_code == 401

    def test_tc_adm_02_stats_four_metrics(self, live):
        r = live.a("get", "/stats")
        assert r.status_code == 200
        s = r.json()
        assert s["total_products"] == 53
        assert s["active_sessions"] >= 0
        assert s["total_customers"] >= 0
        assert isinstance(s["top_products"], list)
        assert isinstance(s["price_mismatch_count"], int)

    def test_tc_adm_03_stats_requires_auth(self, live):
        import httpx

        with httpx.Client(base_url=live.c.base_url, timeout=30) as anon:
            assert anon.get("/api/admin/stats").status_code == 401
            assert anon.get("/api/admin/products").status_code == 401


PAYLOAD = {
    "name": "Áo system-test thêm mới",
    "brand": "Test House",
    "category": "áo",
    "description": "Sản phẩm tạm cho system test — áo thun cotton kiểm thử RAG index.",
    "price_vnd": 250_000,
    "sizes_available": ["S", "M"],
    "colors": ["đỏ"],
    "material": "cotton",
    "stock_per_size": {"S": 1, "M": 2},
    "tags": ["system-test"],
    "gender": "unisex",
}


class TestProductCrud:
    def test_tc_adm_04_crud_cycle_on_sandbox(self, live, catalog):
        before = len(catalog)
        # CREATE
        r = live.a("post", "/products", json=PAYLOAD)
        assert r.status_code == 200
        pid = r.json()["id"]
        try:
            # READ — thấy trong admin list
            listed = live.a("get", "/products").json()
            assert len(listed) == before + 1
            assert any(p["id"] == pid for p in listed)

            # UPDATE một phần
            u = live.a("put", f"/products/{pid}", json={"price_vnd": 199_000})
            assert u.status_code == 200 and u.json()["price_vnd"] == 199_000

            # DELETE
            d = live.a("delete", f"/products/{pid}")
            assert d.status_code == 200 and d.json()["deleted"] == pid
        finally:
            # nếu delete fail thì dọn tay để không leak sang test khác
            listed = live.a("get", "/products").json()
            if any(p["id"] == pid for p in listed):
                live.a("delete", f"/products/{pid}")
        assert len(live.a("get", "/products").json()) == before

    def test_tc_adm_05_stats_total_tracks_crud(self, live):
        base = live.a("get", "/stats").json()["total_products"]
        r = live.a("post", "/products", json={**PAYLOAD, "name": "Áo system-test đếm"})
        pid = r.json()["id"]
        # stats đọc file trực tiếp → thấy ngay, không cần rebuild
        assert live.a("get", "/stats").json()["total_products"] == base + 1
        live.a("delete", f"/products/{pid}")
        assert live.a("get", "/stats").json()["total_products"] == base

    def test_tc_adm_06_orders_list_shape(self, live):
        r = live.a("get", "/orders")
        assert r.status_code == 200
        body = r.json()
        assert set(body) == {"orders", "total", "price_mismatch_count"}
        for row in body["orders"]:
            assert set(row) >= {"order_id", "status", "total_vnd", "price_mismatch"}
            assert row["status"] in {
                "pending", "confirmed", "shipped", "completed", "cancelled", "failed"
            }
