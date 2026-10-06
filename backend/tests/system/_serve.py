"""Trình khởi động server cho system test — app production y nguyên (uvicorn + lifespan
thật + OpenRouter thật), chỉ redirect file state sang sandbox để không bẩn backend/data.

Chạy bởi venv python với env: SYSTEM_SANDBOX (thư mục tmp), SYSTEM_PORT.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
SANDBOX = Path(os.environ["SYSTEM_SANDBOX"])
PORT = int(os.environ["SYSTEM_PORT"])

sys.path.insert(0, str(BACKEND))

# catalog thật (products + embeddings) copy sang sandbox — đọc giống hệt production
for name in ("products.jsonl", "embeddings.npy"):
    shutil.copy(BACKEND / "data" / name, SANDBOX / name)

import app.schemas  # noqa: E402,F401 — trước storage để phá circular schemas↔storage
import app.data.storage as st  # noqa: E402

st.DATA_DIR = SANDBOX
st.CARTS_FILE = SANDBOX / "carts.jsonl"
st.ORDERS_FILE = SANDBOX / "orders.jsonl"
st.CUSTOMER_PROFILES_FILE = SANDBOX / "customer_profiles.jsonl"

import app.rag.index as ri  # noqa: E402

ri.PRODUCTS_FILE = SANDBOX / "products.jsonl"
ri.EMBEDDINGS_FILE = SANDBOX / "embeddings.npy"

# admin/public tham chiếu tên module-level → patch sau import
import app.routes.admin as adm  # noqa: E402
import app.routes.public as pub  # noqa: E402

adm.PRODUCTS_FILE = ri.PRODUCTS_FILE
pub.PRODUCTS_FILE = ri.PRODUCTS_FILE

import uvicorn  # noqa: E402

uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, log_level="warning")
