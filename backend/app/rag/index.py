"""Load products.jsonl + embeddings.npy, cung cấp cho retriever."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np

from ..log import logger
from ..schemas import Product

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PRODUCTS_FILE = DATA_DIR / "products.jsonl"
EMBEDDINGS_FILE = DATA_DIR / "embeddings.npy"


@dataclass
class RagIndex:
    products: List[Product]
    embeddings: np.ndarray  # shape (N, D)
    by_id: Dict[str, int]   # product_id -> row index

    @classmethod
    def load(cls) -> "RagIndex":
        if not PRODUCTS_FILE.exists():
            raise FileNotFoundError(
                f"{PRODUCTS_FILE} chưa tồn tại. Chạy scripts/generate_dataset.py trước."
            )
        products = []
        with PRODUCTS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                products.append(Product.model_validate_json(line))
        if not EMBEDDINGS_FILE.exists():
            raise FileNotFoundError(
                f"{EMBEDDINGS_FILE} chưa tồn tại. Chạy scripts/build_embeddings.py."
            )
        embeddings = np.load(EMBEDDINGS_FILE)
        if embeddings.shape[0] != len(products):
            raise ValueError(
                f"products ({len(products)}) và embeddings ({embeddings.shape[0]}) không khớp. "
                f"Chạy lại scripts/build_embeddings.py.")
        logger.info(f"Loaded RAG index: {len(products)} products, dim={embeddings.shape[1]}")
        by_id = {p.id: i for i, p in enumerate(products)}
        return cls(products=products, embeddings=embeddings, by_id=by_id)

    def save_embeddings(embeddings: np.ndarray) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        np.save(EMBEDDINGS_FILE, embeddings)
        logger.info(f"Saved embeddings shape={embeddings.shape} -> {EMBEDDINGS_FILE}")
