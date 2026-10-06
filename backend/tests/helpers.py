"""Helpers thuần cho unit/integration tests — module name duy nhất để tránh
xung đột `import conftest` khi có nhiều conftest.py trong cây tests/."""
from __future__ import annotations

import json

import numpy as np

import app.schemas  # noqa: F401 — phá circular import app.schemas ↔ app.data.storage
from app.rag.index import RagIndex
from app.schemas import Product

ADMIN_TOKEN = "test-admin-token"

VECS = {
    "P001": [1.0, 0.0, 0.0],
    "P002": [0.9, 0.1, 0.0],
    "P003": [0.0, 1.0, 0.0],
    "P004": [0.0, 0.0, 1.0],
}
DEFAULT_VEC = [0.577, 0.577, 0.577]


def assistant_text(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def assistant_tool(name, args, call_id="c1"):
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
                        }
                    ],
                }
            }
        ]
    }


def assistant_tools(*specs):
    """Một assistant message chứa N tool_calls. specs = [(name, args, call_id), ...]."""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
                        }
                        for name, args, call_id in specs
                    ],
                }
            }
        ]
    }


def make_product(
    pid: str = "P001",
    category: str = "áo",
    price: int = 500_000,
    sizes=("S", "M", "L"),
    stock=None,
    colors=("đen",),
    gender: str = "unisex",
    name: str | None = None,
) -> Product:
    sizes = list(sizes)
    if stock is None:
        stock = {s: 5 for s in sizes}
    return Product(
        id=pid,
        name=name or f"Sản phẩm {pid}",
        brand="Maison Étoile",
        category=category,
        description="Mô tả phục vụ kiểm thử.",
        price_vnd=price,
        sizes_available=sizes,
        colors=list(colors),
        material="cotton",
        stock_per_size=dict(stock),
        tags=["test"],
        image_url="https://example.invalid/img.png",
        gender=gender,
    )


def make_index(products, vectors) -> RagIndex:
    emb = np.asarray(vectors, dtype=np.float32)
    return RagIndex(products=products, embeddings=emb, by_id={p.id: i for i, p in enumerate(products)})


class FakeEmbedder:
    backend = "fake"

    async def embed(self, texts):
        out = []
        for t in texts:
            low = t.lower()
            if "quần" in low or "quan" in low:
                out.append([0.0, 1.0, 0.0])
            elif "váy" in low or "vay" in low:
                out.append([0.0, 0.0, 1.0])
            else:
                out.append([1.0, 0.0, 0.0])
        return out


class FakeLLM:
    """Script trả lời theo hàng đợi; mặc định final text khi hết script.

    Queue một Exception instance để giả lập lỗi từ llm.chat_completion.
    """

    def __init__(self):
        self.script = []
        self.calls = []

    def queue(self, *responses):
        self.script.extend(responses)

    async def __call__(self, messages, tools=None, tool_choice="auto", **kw):
        import copy as _copy

        self.calls.append(_copy.deepcopy(messages))
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return assistant_text("OK")
