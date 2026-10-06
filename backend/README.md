# Backend — Fashion Sales Chatbot

FastAPI + OpenRouter.

## Cài

Yêu cầu **Python 3.11 – 3.13**. `pydantic-core==2.23.4` và `numpy==2.1.3` chưa có
wheel cho cp314; Python 3.14 sẽ ép build từ source (kéo cả Rust toolchain) rồi fail.

```bash
uv venv --python 3.13          # hoặc: python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Chạy lệnh trong thư mục `backend/`. Ở gốc repo không có venv của project — `uv` sẽ
nhặt nhầm `.venv` ở gốc và cài sai chỗ.

Sinh data lần đầu:

```bash
python scripts/generate_dataset.py
python scripts/build_embeddings.py
```

## Chạy dev

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`app/config.py::_find_env_file()` dò `.env` từ thư mục `app/` ngược lên tổ chức và
lấy file **đầu tiên** tìm thấy → `backend/.env` thắng `../.env`. Sửa `CHAT_MODEL`
phải sửa trong `backend/.env`.

Kiểm tra model còn sống trước khi chat (list 396 model hỗ trợ tools):

```bash
curl -s localhost:8000/api/models | python3 -c \
  "import json,sys; print('\n'.join(m['id'] for m in json.load(sys.stdin)['models']))"
```

## Chạy production (một origin, API + static)

```bash
STATIC_DIR=../frontend/dist uvicorn app.server:app --host 0.0.0.0 --port 8000
```

## Test

```bash
pytest -q
```

## Endpoints

### Public
- `GET  /api/health`
- `GET  /api/models` — list model OpenRouter hỗ trợ tools
- `POST /api/chat` — `{session_id, message}` → reply + tool_calls + products
- `GET  /api/products/{id}` — public detail

### Admin (Bearer `<ADMIN_TOKEN>` hoặc cookie `admin_session`)
- `POST /api/admin/login` — `{token}`
- `POST /api/admin/logout`
- `GET  /api/admin/stats`
- `GET  /api/admin/products`
- `POST /api/admin/products`
- `PUT  /api/admin/products/{id}`
- `DELETE /api/admin/products/{id}`
- `POST /api/admin/rebuild-index` — chạy nền