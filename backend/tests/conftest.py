"""Fixtures cho unit + integration test. Helper thuần nằm trong `helpers.py`
(module name duy nhất — tránh xung đột `import conftest` giữa tests/ và tests/system/)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.schemas  # noqa: F401,E402 — import trước để phá circular app.schemas ↔ app.data.storage
from app.data import storage as storage_mod  # noqa: E402
from app.rag.index import RagIndex  # noqa: E402
from app.schemas import Product  # noqa: E402
from helpers import (  # noqa: E402
    ADMIN_TOKEN,
    DEFAULT_VEC,
    VECS,
    FakeEmbedder,
    FakeLLM,
    make_product,
)

from fastapi.testclient import TestClient  # noqa: E402

# autouse: mọi storage file của test process trỏ vào tmp_path của test đó
@pytest.fixture(autouse=True)
def isolated_storage_files(tmp_path, monkeypatch):
    """Redirect mọi đường dẫn JSONL của storage layer sang tmp_path."""
    monkeypatch.setattr(storage_mod, "CARTS_FILE", tmp_path / "carts.jsonl")
    monkeypatch.setattr(storage_mod, "ORDERS_FILE", tmp_path / "orders.jsonl")
    monkeypatch.setattr(storage_mod, "CUSTOMER_PROFILES_FILE", tmp_path / "profiles.jsonl")


@pytest.fixture
def products():
    """3 sản phẩm 3 danh mục, vector trực chuẩn → cosine có thứ tự dự đoán được."""
    return [
        make_product("P001", "áo", 450_000, colors=("đen", "trắng"), gender="nam"),
        make_product("P002", "quần", 890_000, sizes=("M", "L"), colors=("xanh",), gender="nam"),
        make_product("P003", "váy", 1_200_000, sizes=("S", "M"), colors=("trắng",), gender="nữ"),
    ]


@pytest.fixture
def rag_index(products):
    import numpy as np

    return RagIndex(
        products=products,
        embeddings=np.asarray(
            [[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32
        ),
        by_id={p.id: i for i, p in enumerate(products)},
    )


# =========================================================================
# API integration fixtures — app thật (TestClient) với world cô lập:
#   - file JSONL + products.jsonl → tmp_path
#   - OpenRouter thay bằng FakeLLM (script) + FakeEmbedder deterministic
# =========================================================================
@pytest.fixture
def api_env(tmp_path, monkeypatch):
    """Thế giới cô lập cho một lần dựng app: file tmp, singleton reset, LLM/Embedder fake."""
    import numpy as np

    import app.main as main_mod
    import app.routes.admin as admin_mod
    import app.routes.chat as chat_mod
    import app.routes.public as public_mod
    import app.session as session_mod
    from app.rag import index as index_mod

    products = [
        make_product("P001", "áo", 450_000, sizes=("S", "M"), stock={"S": 2, "M": 5}, colors=("đen",)),
        make_product("P002", "áo", 600_000, sizes=("M",), stock={"M": 1}, colors=("trắng",)),
        make_product("P003", "quần", 890_000, sizes=("M",), stock={"M": 0}, colors=("xanh",)),
        make_product("P004", "váy", 1_200_000, sizes=("S",), stock={"S": 3}, colors=("trắng",)),
    ]
    products_file = tmp_path / "products.jsonl"
    with products_file.open("w", encoding="utf-8") as f:
        for p in products:
            f.write(p.model_dump_json() + "\n")

    monkeypatch.setattr(admin_mod, "PRODUCTS_FILE", products_file)
    monkeypatch.setattr(public_mod, "PRODUCTS_FILE", products_file)

    def _fake_load():
        prods = []
        with products_file.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    prods.append(Product.model_validate_json(line))
        emb = np.asarray([VECS.get(p.id, DEFAULT_VEC) for p in prods], dtype=np.float32)
        return RagIndex(products=prods, embeddings=emb, by_id={p.id: i for i, p in enumerate(prods)})

    monkeypatch.setattr(index_mod.RagIndex, "load", staticmethod(_fake_load))

    # reset singleton stores để tạo lại trên file tmp của test này
    monkeypatch.setattr(session_mod, "_store", None)
    for name in ("_cart_store", "_order_store", "_profile_store"):
        monkeypatch.setattr(storage_mod, name, None)
    admin_mod._admin_sessions.clear()

    # config xác định (không phụ thuộc .env của repo)
    monkeypatch.setattr(admin_mod, "get_settings", lambda: SimpleNamespace(admin_token=ADMIN_TOKEN))
    monkeypatch.setattr(session_mod, "get_settings", lambda: SimpleNamespace(session_ttl_seconds=1800))

    # lifespan: bỏ warmup network, Embedder fake
    async def _noop_warmup():
        return None

    monkeypatch.setattr(main_mod, "warmup_or_die", _noop_warmup)
    monkeypatch.setattr(main_mod, "Embedder", FakeEmbedder)

    # public /api/models: không gọi OpenRouter thật
    async def _no_models():
        return []

    monkeypatch.setattr(public_mod, "list_supported_models", _no_models)

    # chat route: LLM fake theo script
    fake_llm = FakeLLM()
    monkeypatch.setattr(chat_mod, "chat_completion", fake_llm)

    return SimpleNamespace(
        products=products,
        products_file=products_file,
        fake_llm=fake_llm,
        admin_token=ADMIN_TOKEN,
    )


@pytest.fixture
def client(api_env):
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def admin_auth(api_env):
    return {"Authorization": f"Bearer {api_env.admin_token}"}


@pytest.fixture
def cart(client):
    """Tạo cart qua REST; trả (cart_id, headers)."""
    r = client.post("/api/cart")
    assert r.status_code == 200
    body = r.json()
    return body["cart_id"], {"X-Cart-Token": body["cart_token"]}
