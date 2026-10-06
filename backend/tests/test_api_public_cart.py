"""Integration — public API + cart REST qua FastAPI TestClient (app + routes + storage thật)."""
from __future__ import annotations


class TestPublicApi:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_list_products_pagination_and_total(self, client):
        r = client.get("/api/products", params={"limit": 2})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 4
        assert len(body["items"]) == 2

    def test_filter_price_range_and_search(self, client):
        r = client.get("/api/products", params={"min_price": 500_000, "max_price": 1_000_000})
        assert {p["id"] for p in r.json()["items"]} == {"P002", "P003"}
        r2 = client.get("/api/products", params={"search": "P004"})
        # search khớp theo name/description/brand — "Sản phẩm P004" chứa chuỗi
        assert {p["id"] for p in r2.json()["items"]} == {"P004"}


class TestCartRest:
    def test_get_requires_token(self, client, cart):
        cid, headers = cart
        assert client.get(f"/api/cart/{cid}").status_code == 401
        assert client.get(f"/api/cart/{cid}", headers={"X-Cart-Token": "wrong"}).status_code == 401
        assert client.get("/api/cart/ghost", headers=headers).status_code == 404
        ok = client.get(f"/api/cart/{cid}", headers=headers)
        assert ok.status_code == 200
        assert "cart_token" not in ok.json()  # CartView không lộ token

    def test_add_update_delete_roundtrip(self, client, cart):
        cid, headers = cart
        r = client.post(
            f"/api/cart/{cid}/items",
            headers=headers,
            json={"product_id": "P001", "size": "M", "quantity": 2},
        )
        assert r.status_code == 200
        view = r.json()
        assert view["total_vnd"] == 450_000 * 2
        assert view["items"][0]["price_vnd_snapshot"] == 450_000

        r2 = client.put(
            f"/api/cart/{cid}/items/P001/M", headers=headers, json={"quantity": 3}
        )
        assert r2.json()["total_vnd"] == 450_000 * 3

        r3 = client.delete(f"/api/cart/{cid}/items/P001/M", headers=headers)
        assert r3.status_code == 200 and r3.json()["items"] == []

    def test_add_zero_stock_400(self, client, cart):
        """P003 size M stock=0 → 400 hết hàng."""
        cid, headers = cart
        r = client.post(
            f"/api/cart/{cid}/items",
            headers=headers,
            json={"product_id": "P003", "size": "M", "quantity": 1},
        )
        assert r.status_code == 400

