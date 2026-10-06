"""TC-CART — hành trình mua hàng trên hệ thống thật (mục 5.4.2).

Phần giỏ/đơn làm qua REST (xác định, không LLM); phần chốt đơn làm qua CHAT với
LLM thật để kiểm chứng chuỗi update_customer_profile → create_order + admin duyệt.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.system

PHONE = "0900000111"
NAME = "Nguyễn Văn TestSys"
ADDR = "1 Lê Lợi, Quận 1, TP.HCM"


def pick_in_stock(catalog, category=None):
    for p in catalog.values():
        if category and p["category"] != category:
            continue
        for size, qty in p["stock_per_size"].items():
            if qty > 0:
                return p, size
    raise AssertionError("catalog không có sản phẩm còn hàng")


class TestCartRestJourney:
    def test_tc_cart_01_add_snapshot_total(self, live, catalog):
        p, size = pick_in_stock(catalog, "áo")
        cid, headers = live.create_cart()
        r = live.add_item(cid, headers, p["id"], size, 2)
        assert r.status_code == 200
        view = r.json()
        assert view["items"][0]["price_vnd_snapshot"] == p["price_vnd"]
        assert view["total_vnd"] == p["price_vnd"] * 2

    def test_tc_cart_02_bad_inputs_rejected(self, live, catalog):
        p, size = pick_in_stock(catalog)
        cid, headers = live.create_cart()
        # size không tồn tại trên sản phẩm → 400
        assert live.add_item(cid, headers, p["id"], "ZZZ", 1).status_code == 400
        # sản phẩm ma → 404
        assert live.add_item(cid, headers, "PXXXX", size, 1).status_code == 404
        # quá tồn kho → 400
        assert live.add_item(cid, headers, p["id"], size, 999).status_code == 400
        # không có token → 401
        assert live.c.get(f"/api/cart/{cid}").status_code == 401

    def test_tc_cart_03_quantity_edit_roundtrip(self, live, catalog):
        p, size = pick_in_stock(catalog)
        cid, headers = live.create_cart()
        live.add_item(cid, headers, p["id"], size, 1)
        r = live.c.put(
            f"/api/cart/{cid}/items/{p['id']}/{size}",
            headers=headers,
            json={"quantity": 2},
        )
        assert r.status_code == 200 and r.json()["items"][0]["quantity"] == 2
        r2 = live.c.delete(f"/api/cart/{cid}/items/{p['id']}/{size}", headers=headers)
        assert r2.status_code == 200 and r2.json()["items"] == []


class TestChatOrderJourney:
    def test_tc_order_01_full_flow(self, live, catalog):
        """REST giỏ → chat tạo đơn → khách tra đơn → admin duyệt → đơn hoàn tất."""
        p, size = pick_in_stock(catalog)
        cid, headers = live.create_cart()
        assert live.add_item(cid, headers, p["id"], size, 1).status_code == 200
        token = headers["X-Cart-Token"]

        # 1. Cung cấp thông tin + chốt đơn qua chat (LLM thật quyết định tool-call)
        r1 = live.chat(
            "sys-buy-1",
            f"Tên mình {NAME}, số điện thoại {PHONE}, địa chỉ {ADDR}. "
            "Đặt hàng giùm mình, xác nhận luôn nhé.",
            cart=(cid, token),
        )
        assert r1.status_code == 200, r1.text
        tools = [tc["tool"] for tc in r1.json()["tool_calls"]]
        assert "update_customer_profile" in tools, tools
        if "create_order" not in tools:
            # mô hình free đôi khi hỏi lại xác nhận — đáp vâng và chờ tool-call
            r1 = live.chat(
                "sys-buy-1",
                f"Vâng, xác nhận đặt đơn. Số điện thoại {PHONE}.",
                cart=(cid, token),
            )
            tools = [tc["tool"] for tc in r1.json()["tool_calls"]]
        assert "create_order" in tools, (
            f"LLM không gọi create_order sau khi khách xác nhận: {tools}"
        )

        # 2. Khách tra đơn bằng SĐT — pending, total khớp snapshot
        mine = live.my_orders(PHONE).json()
        assert mine, "không thấy đơn của khách"
        order = mine[-1]
        assert order["status"] == "pending"
        assert order["total_vnd"] == p["price_vnd"]
        oid = order["order_id"]

        # 3. Admin duyệt pending → confirmed → shipped → completed
        t = None
        for status in ("confirmed", "shipped", "completed"):
            t = live.a("post", f"/orders/{oid}/transition", json={"new_status": status})
            assert t.status_code == 200, t.text
            assert t.json()["status"] == status
        assert [h["status"] for h in t.json()["status_history"]] == [
            "pending", "confirmed", "shipped", "completed",
        ]

        # 4. Khách tra lại thấy completed; nhảy trạng thái trái bảng bị chặn
        assert live.my_orders(PHONE).json()[-1]["status"] == "completed"
        after = live.a("post", f"/orders/{oid}/transition", json={"new_status": "pending"})
        assert after.status_code == 422

    def test_tc_order_02_price_snapshot_after_catalog_edit(self, live, catalog):
        """Sửa giá sau khi tạo đơn → đơn giữ giá snapshot; dashboard flag mismatch (ADR-0008)."""
        p, size = pick_in_stock(catalog, category="quần")
        cid, headers = live.create_cart()
        live.add_item(cid, headers, p["id"], size, 1)
        phone2 = "0900000222"
        r = live.chat(
            "sys-buy-2",
            f"Ghi nhận thông tin: {NAME}, {phone2}, {ADDR}. Đặt đơn từ giỏ hiện tại giúp mình.",
            cart=(cid, headers["X-Cart-Token"]),
        )
        tools = [tc["tool"] for tc in r.json()["tool_calls"]]
        if "create_order" not in tools:
            r = live.chat(
                "sys-buy-2",
                f"Vâng, xác nhận. Số điện thoại {phone2}.",
                cart=(cid, headers["X-Cart-Token"]),
            )
            tools = [tc["tool"] for tc in r.json()["tool_calls"]]
        assert "create_order" in tools, tools

        order = live.my_orders(phone2).json()[-1]
        new_price = p["price_vnd"] + 300_000
        u = live.a("put", f"/products/{p['id']}", json={"price_vnd": new_price})
        assert u.status_code == 200
        try:
            again = live.my_orders(phone2).json()[-1]
            assert again["items"][0]["price_vnd_snapshot"] == p["price_vnd"]
            assert again["total_vnd"] == p["price_vnd"]
            stats = live.a("get", "/stats").json()
            assert stats["price_mismatch_count"] >= 1
        finally:
            # trả giá cũ + đóng đơn để không ảnh hưởng các bài khác
            live.a("put", f"/products/{p['id']}", json={"price_vnd": p["price_vnd"]})
            if order["status"] == "pending":
                live.a(
                    "post",
                    f"/orders/{order['order_id']}/transition",
                    json={"new_status": "cancelled"},
                )
