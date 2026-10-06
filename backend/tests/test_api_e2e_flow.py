"""Integration end-to-end — toàn bộ nghiệp vụ mua hàng qua 2 giao diện (REST + chat tool-loop).

Kiểm chứng các bất biến xuyên suốt: giỏ hàng dùng chung giữa REST và chat,
snapshot giá bất biến khi catalog đổi, phân quyền khách/admin trên đơn hàng.
"""
from __future__ import annotations

from helpers import assistant_text, assistant_tool


class TestFullPurchaseJourney:
    def test_browse_cart_order_delivery_tracking(self, client, api_env, admin_auth):
        # 1. Khách tìm hàng bằng REST
        browse = client.get("/api/products", params={"category": "áo", "max_price": 500_000}).json()
        assert [p["id"] for p in browse["items"]] == ["P001"]

        # 2. Tạo giỏ, thêm hàng qua REST
        created = client.post("/api/cart").json()
        cid, headers = created["cart_id"], {"X-Cart-Token": created["cart_token"]}
        add = client.post(
            f"/api/cart/{cid}/items",
            headers=headers,
            json={"product_id": "P001", "size": "M", "quantity": 2},
        )
        assert add.json()["total_vnd"] == 900_000

        # 3. Chat dùng CHÍNH giỏ đó: gợi ý bổ trợ cho váy/áo rồi chốt đơn
        api_env.fake_llm.queue(
            assistant_tool("recommend_similar", {"mode": "complement", "k": 2}),
            assistant_tool("update_customer_profile", {
                "phone": "0905111222", "name": "Trần B", "address": "25 Hai Bà Trưng",
            }),
            assistant_tool("create_order", {"phone": "0905111222"}),
            assistant_text("Đơn của anh/chị đang chờ shop xác nhận."),
        )
        chat = client.post(
            "/api/chat",
            json={
                "session_id": "journey", "message": "chốt đơn giúp mình",
                "cart_id": cid, "cart_token": created["cart_token"],
            },
        )
        assert chat.status_code == 200
        assert [tc["tool"] for tc in chat.json()["tool_calls"]] == [
            "recommend_similar", "update_customer_profile", "create_order",
        ]

        # 4. Giỏ vẫn nguyên sau khi tạo đơn (snapshot, không auto-clear)
        assert len(client.get(f"/api/cart/{cid}", headers=headers).json()["items"]) == 1

        # 5. Khách tra đơn bằng số điện thoại
        mine = client.get("/api/orders/me", params={"phone": "0905111222"}).json()
        assert len(mine) == 1
        order = mine[0]
        assert order["status"] == "pending"
        assert order["total_vnd"] == 900_000
        assert order["customer_name"] == "Trần B"
        assert order["items"][0]["price_vnd_snapshot"] == 450_000

        # 6. Admin duyệt: pending → confirmed → shipped → completed
        oid = order["order_id"]
        for status in ("confirmed", "shipped", "completed"):
            t = client.post(
                f"/api/admin/orders/{oid}/transition",
                headers=admin_auth,
                json={"new_status": status},
            )
            assert t.status_code == 200 and t.json()["status"] == status
        history = [h["status"] for h in t.json()["status_history"]]
        assert history == ["pending", "confirmed", "shipped", "completed"]

        # 7. Khách KHÔNG có endpoint đổi trạng thái — chỉ admin mới chuyển được
        #    (đơn đã completed, kể cả admin cũng không chuyển tiếp được)
        after = client.post(
            f"/api/admin/orders/{oid}/transition",
            headers=admin_auth,
            json={"new_status": "cancelled"},
        )
        assert after.status_code == 422

    def test_price_snapshot_survives_catalog_edit(self, client, api_env, admin_auth):
        """Bất biến CORE của ADR: sửa giá catalog không làm đổi đơn đã tạo."""
        created = client.post("/api/cart").json()
        cid, headers = created["cart_id"], {"X-Cart-Token": created["cart_token"]}
        client.post(
            f"/api/cart/{cid}/items",
            headers=headers,
            json={"product_id": "P004", "size": "S", "quantity": 1},
        )
        api_env.fake_llm.queue(
            assistant_tool("update_customer_profile", {
                "phone": "0906333444", "name": "Lê C", "address": "8 Võ Văn Tần",
            }),
            assistant_tool("create_order", {"phone": "0906333444"}),
            assistant_text("Xong rồi ạ."),
        )
        client.post(
            "/api/chat",
            json={"session_id": "snap", "message": "đặt váy",
                  "cart_id": cid, "cart_token": created["cart_token"]},
        )
        order = client.get("/api/orders/me", params={"phone": "0906333444"}).json()[0]
        assert order["items"][0]["price_vnd_snapshot"] == 1_200_000

        # Admin đổi giá + đổi tên sản phẩm
        client.put(
            "/api/admin/products/P004",
            headers=admin_auth,
            json={"price_vnd": 2_500_000, "name": "Váy deadline mới"},
        )
        again = client.get("/api/orders/me", params={"phone": "0906333444"}).json()[0]
        assert again["items"][0]["price_vnd_snapshot"] == 1_200_000
        assert again["items"][0]["name_snapshot"] == "Sản phẩm P004"
        assert again["total_vnd"] == 1_200_000

        # ...và dashboard flag đơn pending có chênh lệch giá
        assert client.get("/api/admin/stats", headers=admin_auth).json()[
            "price_mismatch_count"
        ] == 1

    def test_admin_dashboard_counts_this_journey(self, client, api_env, admin_auth):
        created = client.post("/api/cart").json()
        api_env.fake_llm.queue(
            assistant_tool("search_products", {"query": "quần", "category": "quần"}),
            assistant_text("Mình có một mẫu quần."),
        )
        client.post(
            "/api/chat",
            json={"session_id": "dash", "message": "tìm quần",
                  "cart_id": created["cart_id"], "cart_token": created["cart_token"]},
        )
        s = client.get("/api/admin/stats", headers=admin_auth).json()
        assert s["total_products"] == 4
        assert s["active_sessions"] == 1
        assert s["total_customers"] == 1
        # /stats enrich top_products với name từ index
        assert {"id": "P003", "name": "Sản phẩm P003", "count": 1} in s["top_products"]
