"""Production server entrypoint — app FastAPI + serve static frontend cùng origin.

Khác `app.main:app` (dev, CORS qua Vite proxy): `app.server:app` mount thư mục
`/app/static` (Docker build đổ `frontend/dist` vào đó) lên `/` — một origin duy nhất,
KHÔNG cần CORS trong production. Không có thư mục static → chỉ API (đầu backend thuần).
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .main import app  # tái sử dụng toàn bộ router + lifespan

STATIC_DIR = Path(os.environ.get("STATIC_DIR", "/app/static"))

if STATIC_DIR.is_dir():
    # SPA fallback: mọi route không phải /api trả index.html để React Router xử lý
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
