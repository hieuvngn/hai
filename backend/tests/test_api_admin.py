"""Integration — admin API: auth (Bearer + cookie), stats, CRUD sản phẩm, orders transition."""
from __future__ import annotations

from helpers import assistant_text, assistant_tool, assistant_tools


def seed_order(client, api_env, phone="0900123456", items=(("P001", "M", 2),)):
    """Tạo đơn qua đúng luồng production: REST cart + /api/chat tool-loop (FakeLLM script).

    Mọi thao tác storage chạy trong event loop của app (TestClient portal) —
    không đụng singleton store từ loop của test (asyncio.Lock bị bind theo loop).
    """
    created = client.post("/api/cart").json()
    cid, token = created["cart_id"], created["cart_token"]

    script = []
    for pid, size, qty in items:
        script.append(assistant_tool("add_to_cart", {"product_id": pid, "size": size, "quantity": qty}))
    script.append(assistant_tool("update_customer_profile", {"phone": phone, "name": "Khách A", "address": "1 Lê Lợi"}))
    script.append(assistant_tool("create_order", {"phone": phone}))
    script.append(assistant_text("Đã tạo đơn hàng."))
    api_env.fake_llm.queue(*script)

    r = client.post(
        "/api/chat",
        json={"session_id": "seed-s", "message": "đặt hàng", "cart_id": cid, "cart_token": token},
    )
    assert r.status_code == 200, r.text
    tools = [tc["tool"] for tc in r.json()["tool_calls"]]
    assert tools.count("create_order") == 1, tools

    mine = client.get("/api/orders/me", params={"phone": phone}).json()
    assert mine, "create_order không tạo được đơn"
    return mine[-1]


class TestAdminAuth:
    def test_protected_endpoints_reject_anonymous(self, client):
        assert client.get("/api/admin/stats").status_code == 401
        assert client.get("/api/admin/products").status_code == 401
        assert client.get("/api/admin/orders").status_code == 401

    def test_login_sets_cookie_usable_for_subsequent_requests(self, client, api_env):
        bad = client.post("/api/admin/login", json={"token": "sai"})
        assert bad.status_code == 401
        good = client.post("/api/admin/login", json={"token": api_env.admin_token})
        assert good.status_code == 200 and good.json() == {"ok": True}
        assert good.cookies.get("admin_session")
        # Cookie phải tự xác thực được — không cần header Authorization.
        assert client.get("/api/admin/stats").status_code == 200

    def test_forged_cookie_rejected(self, client):
        r = client.get("/api/admin/stats", headers={"Cookie": "admin_session=sid-tu-bia"})
        assert r.status_code == 401


class TestProductCrud:
    def payload(self, **over):
        base = dict(
            name="Áo khoác jeans",
            brand="Linh & Co",
            category="áo",
            description="Áo khoác denim.",
            price_vnd=700_000,
            sizes_available=["M", "L"],
            colors=["xanh"],
            material="denim",
            stock_per_size={"M": 4, "L": 2},
            tags=["test"],
            gender="unisex",
        )
        base.update(over)
        return base

    def test_create_assigns_next_id_and_default_image(self, client, admin_auth, api_env):
        r = client.post("/api/admin/products", headers=admin_auth, json=self.payload())
        assert r.status_code == 200
        p = r.json()
        # _next_id dùng format P{n:04d}; P001–P004 (3 số) không trùng khuôn → P0001
        assert p["id"] == "P0001"
        assert p["image_url"] == "https://picsum.photos/seed/P0001/400/400"
        assert "P0001" in api_env.products_file.read_text(encoding="utf-8")
        # /api/products đọc app.state.rag_index (stale by design tới khi rebuild)
        # → verify qua /api/admin/products (đọc file trực tiếp)
        ids = {x["id"] for x in client.get("/api/admin/products", headers=admin_auth).json()}
        assert "P0001" in ids

    def test_invalid_enum_rejected(self, client, admin_auth):
        r = client.post("/api/admin/products", headers=admin_auth, json=self.payload(category="sách"))
        assert r.status_code == 422


class TestStatsAndOrders:
    def test_stats_counts_products_sessions_customers(self, client, admin_auth):
        client.post("/api/chat", json={"session_id": "s-live", "message": "xin chào"})
        s = client.get("/api/admin/stats", headers=admin_auth).json()
        assert s["total_products"] == 4
        assert s["active_sessions"] >= 1
        assert s["total_customers"] == 1

    def test_top_products_counts_each_product_once_per_turn(self, client, admin_auth, api_env):
        """Một lượt gọi 2 tool trả về sản phẩm → mỗi sản phẩm chỉ được tính 1 lần.

        Nếu route /api/chat truyền danh sách gom tích luỹ (thay vì sản phẩm của
        chính tool-call đó) xuống bộ đếm, sản phẩm của tool-call đầu bị đếm lại
        ở tool-call sau và top_products trên dashboard bị thổi phồng.
        """
        api_env.fake_llm.queue(
            assistant_tools(
                ("get_product", {"product_id": "P001"}, "t1"),
                ("get_product", {"product_id": "P002"}, "t2"),
            ),
            assistant_text("Xong."),
        )
        r = client.post("/api/chat", json={"session_id": "s-count", "message": "2 sản phẩm"})
        assert r.status_code == 200
        assert [tc["tool"] for tc in r.json()["tool_calls"]] == ["get_product", "get_product"]

        top = {e["id"]: e["count"] for e in client.get("/api/admin/stats", headers=admin_auth).json()["top_products"]}
        assert top.get("P001") == 1, top
        assert top.get("P002") == 1, top

    def test_transition_flow_and_illegal_jump(self, client, admin_auth, api_env):
        o = seed_order(client, api_env)
        r = client.post(
            f"/api/admin/orders/{o['order_id']}/transition",
            headers=admin_auth,
            json={"new_status": "confirmed"},
        )
        assert r.status_code == 200 and r.json()["status"] == "confirmed"
        bad = client.post(
            f"/api/admin/orders/{o['order_id']}/transition",
            headers=admin_auth,
            json={"new_status": "pending"},
        )
        assert bad.status_code == 422
        missing = client.post(
            "/api/admin/orders/ORD-ghost/transition",
            headers=admin_auth,
            json={"new_status": "confirmed"},
        )
        assert missing.status_code == 404

