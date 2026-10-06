"""Build embeddings cho toàn bộ products.jsonl, cache xuống data/embeddings.npy.

Chạy:
    cd backend
    python scripts/build_embeddings.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.log import configure_logging, logger  # noqa: E402
from app.rag import EMBEDDINGS_FILE, PRODUCTS_FILE  # noqa: E402
from app.rag.embedder import Embedder  # noqa: E402
from app.schemas import Product  # noqa: E402


def _load_products() -> list[Product]:
    if not PRODUCTS_FILE.exists():
        logger.error(f"{PRODUCTS_FILE} không tồn tại. Chạy scripts/generate_dataset.py trước.")
        sys.exit(1)
    out = []
    with PRODUCTS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(Product.model_validate_json(line))
    return out


async def main():
    configure_logging()
    get_settings()  # trigger env load
    products = _load_products()
    logger.info(f"Build embeddings cho {len(products)} sản phẩm")

    embedder = Embedder()
    texts = [p.to_embedding_text() for p in products]
    vectors = await embedder.embed(texts)
    arr = np.asarray(vectors, dtype=np.float32)
    if arr.shape[0] != len(products):
        logger.error(f"Vector count {arr.shape[0]} != product count {len(products)}")
        sys.exit(1)

    EMBEDDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    np.save(EMBEDDINGS_FILE, arr)
    logger.info(f"Đã lưu embeddings shape={arr.shape} vào {EMBEDDINGS_FILE}")
    logger.info(f"Backend dùng embedder: {embedder.backend}")


if __name__ == "__main__":
    asyncio.run(main())
