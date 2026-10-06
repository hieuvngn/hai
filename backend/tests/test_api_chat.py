"""Integration — POST /api/chat: vòng lặp tool-calling với FakeLLM script.

Kiểm chứng sự ghép nối thật: route → session store → DISPATCH handlers →
embedder → RAG index → cart/profile/order storage, và cách lỗi được chuyển thành HTTP status.
"""
from __future__ import annotations

import json

from app.llm import FatalError
from helpers import assistant_text, assistant_tool


def parse_tool_messages(calls):
    """Lấy list tool message (dict đã parse) từ messages của lượt gọi LLM cuối."""
    last = calls[-1]
    return [json.loads(m["content"]) for m in last if m["role"] == "tool"]


class TestSimpleTurn:
    def test_plain_text_reply_persists_history(self, client, api_env):
        api_env.fake_llm.queue(assistant_text("Xin chào! Mình có thể giúp gì?"))
        r = client.post("/api/chat", json={"session_id": "s1", "message": "xin chào"})
        assert r.status_code == 200
        body = r.json()
        assert body["reply"] == "Xin chào! Mình có thể giúp gì?"
        assert body["tool_calls"] == [] and body["products"] == []
        # lượt kế tiếp: history phải có đủ user + assistant của lượt trước
        api_env.fake_llm.queue(assistant_text("Tạm biệt!"))
        client.post("/api/chat", json={"session_id": "s1", "message": "bye"})
        msgs = api_env.fake_llm.calls[-1]
        assert [m["role"] for m in msgs[:4]] == ["system", "user", "assistant", "user"]
        assert msgs[0]["content"].startswith("Bạn là nhân viên tư vấn")  # system prompt

    def test_two_sessions_are_isolated(self, client, api_env):
        client.post("/api/chat", json={"session_id": "a", "message": "hello A"})
        client.post("/api/chat", json={"session_id": "b", "message": "hello B"})
        roles = [m["content"] for m in api_env.fake_llm.calls[-1] if m["role"] == "user"]
        assert roles == ["hello B"]  # session b không thấy lịch sử của a


class TestSearchToolLoop:
    def test_llm_tool_call_executes_rag_and_returns_products(self, client, api_env):
        api_env.fake_llm.queue(
            assistant_tool("search_products", {"query": "áo sơ mi", "category": "áo"}),
            assistant_text("Mình tìm thấy 2 mẫu áo phù hợp."),
        )
        r = client.post("/api/chat", json={"session_id": "s-search", "message": "tìm áo"})
        body = r.json()
        assert body["reply"] == "Mình tìm thấy 2 mẫu áo phù hợp."
        assert [tc["tool"] for tc in body["tool_calls"]] == ["search_products"]
        assert {p["id"] for p in body["products"]} == {"P001", "P002"}

        # vòng lặp 2: LLM phải thấy tool message chứa kết quả thật
        tool_msgs = parse_tool_messages(api_env.fake_llm.calls)
        assert tool_msgs[0]["found"] == 2
        assert tool_msgs[0]["products"][0]["id"] == "P001"

    def test_unknown_tool_from_llm_yields_error_payload(self, client, api_env):
        api_env.fake_llm.queue(
            assistant_tool("fly_to_moon", {}),
            assistant_text("Xin lỗi, mình không làm được việc đó."),
        )
        r = client.post("/api/chat", json={"session_id": "s-badt", "message": "?"})
        assert r.status_code == 200
        assert "không tồn tại" in parse_tool_messages(api_env.fake_llm.calls)[0]["error"]


class TestCartThroughChat:
    def test_add_to_cart_with_cart_context(self, client, api_env, cart):
        cid, headers = cart
        token = headers["X-Cart-Token"]
        api_env.fake_llm.queue(
            assistant_tool("add_to_cart", {"product_id": "P001", "size": "M", "quantity": 1}),
            assistant_text("Đã thêm vào giỏ."),
        )
        r = client.post(
            "/api/chat",
            json={"session_id": "s-cart", "message": "thêm áo M", "cart_id": cid, "cart_token": token},
        )
        assert r.status_code == 200
        # giỏ hàng dùng chung thấy kết quả từ chat — hai đường ghi đọc cùng store
        got = client.get(f"/api/cart/{cid}", headers=headers).json()
        assert len(got["items"]) == 1
        assert got["total_vnd"] == 450_000


class TestFailureModes:
    def test_fatal_llm_error_becomes_502(self, client, api_env):
        api_env.fake_llm.queue(FatalError("model not found"))
        r = client.post("/api/chat", json={"session_id": "s-fatal", "message": "hi"})
        assert r.status_code == 502
        assert "OpenRouter" in r.json()["detail"]

