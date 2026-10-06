"""System test harness — boot server THẬT (uvicorn subprocess, lifespan thật, OpenRouter
thật) trên sandbox state riêng. Catalog: products.jsonl + embeddings.npy thật của backend.

Chạy:  .venv/bin/python -m pytest tests/system -m system -v
Cần:   OPENROUTER_API_KEY hợp lệ trong .env (đã có trong repo settings).
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/ (conftest, helpers)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/ (app package)

BACKEND = Path(__file__).resolve().parents[2]
SERVE = Path(__file__).resolve().parent / "_serve.py"

pytestmark = pytest.mark.system


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    """Khởi động server sandbox; fail-fast nếu OpenRouter key thiếu/sai."""
    from app.config import get_settings

    settings = get_settings()
    if not settings.openrouter_api_key:
        pytest.skip("OPENROUTER_API_KEY rỗng — không chạy được system test với LLM thật")

    sandbox = tmp_path_factory.mktemp("live-sandbox")
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, str(SERVE)],
        env={**os.environ, "SYSTEM_SANDBOX": str(sandbox), "SYSTEM_PORT": str(port)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    ready = False
    for _ in range(120):  # warmup_or_die gọi /v1/models thật — có thể chậm
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else ""
            pytest.fail(f"Server chết khi khởi động (rc={proc.returncode}):\n{out[-2000:]}")
        try:
            if httpx.get(f"{base}/api/health", timeout=2).status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)
    if not ready:
        proc.terminate()
        pytest.fail("Server không ready trong 60s (nghẽn OpenRouter?)")
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def live(live_server):
    """Client httpx chỉ tới server thật + helper chat có retry vì free-tier 429."""

    class LiveAPI:
        def __init__(self, base: str, token: str):
            self.c = httpx.Client(base_url=base, timeout=90)
            self.token = token

        # ---- public ----
        def health(self):
            return self.c.get("/api/health")

        def products(self, **params):
            return self.c.get("/api/products", params=params)

        def product(self, pid):
            return self.c.get(f"/api/products/{pid}")

        # ---- chat với backoff cho 502 (lỗi transient OpenRouter) ----
        def chat(self, session_id, message, cart=None, tries=4):
            payload = {"session_id": session_id, "message": message}
            if cart:
                payload["cart_id"], payload["cart_token"] = cart
            last = None
            for i in range(tries):
                r = self.c.post("/api/chat", json=payload, timeout=120)
                last = r
                if r.status_code in (502, 500) and i < tries - 1:
                    time.sleep(3 * (i + 1))
                    continue
                return r
            return last

        # ---- cart ----
        def create_cart(self):
            r = self.c.post("/api/cart")
            r.raise_for_status()
            b = r.json()
            return b["cart_id"], {"X-Cart-Token": b["cart_token"]}

        def cart(self, cid, headers):
            return self.c.get(f"/api/cart/{cid}", headers=headers)

        def add_item(self, cid, headers, product_id, size, quantity=1):
            return self.c.post(
                f"/api/cart/{cid}/items",
                headers=headers,
                json={"product_id": product_id, "size": size, "quantity": quantity},
            )

        # ---- orders (khách) ----
        def my_orders(self, phone):
            return self.c.get("/api/orders/me", params={"phone": phone})

        # ---- admin ----
        def a(self, method, path, **kw):
            headers = kw.pop("headers", {})
            headers.setdefault("Authorization", f"Bearer {self.token}")
            return self.c.request(method, f"/api/admin{path}", headers=headers, **kw)

    from app.config import get_settings

    return LiveAPI(live_server, get_settings().admin_token)


@pytest.fixture(scope="session")
def catalog(live):
    """Toàn bộ sản phẩm thật trong index, theo id."""
    items, offset = [], 0
    while True:
        r = live.products(limit=100, offset=offset)
        r.raise_for_status()
        b = r.json()
        items += b["items"]
        if len(items) >= b["total"]:
            break
        offset += 100
    return {p["id"]: p for p in items}
