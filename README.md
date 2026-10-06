# Fashion Sales Chatbot

Chatbot tư vấn bán hàng thời trang — **RAG + Function Calling** qua OpenRouter API.

- **Backend**: Python (FastAPI), gọi OpenRouter (chat + embeddings), local fallback.
- **Frontend**: React + TypeScript (Vite + Tailwind + shadcn/ui).
- **Domain model & ADRs**: xem `CONTEXT.md` và `docs/adr/`.

## Cấu trúc

```
btl_ttnt_hai/
├── backend/         FastAPI + scripts
├── frontend/        Vite + React + TS
├── docs/adr/        6 ADRs
├── CONTEXT.md       glossary
└── .env.example
```

## Yêu cầu

- Python 3.11 – 3.13 (**không dùng 3.14+**: `pydantic-core==2.23.4` / `numpy==2.1.3` chưa có wheel cp314 → build từ source rồi fail)
- Node.js 20+
- OpenRouter API key (lấy tại https://openrouter.ai/keys)

## Setup lần đầu

### 1. Cấu hình `.env`

```bash
cp .env.example backend/.env
# Sửa OPENROUTER_API_KEY=sk-or-v1-... (key của bạn)
# CHAT_MODEL mặc định trong .env.example đã chết — xem mục "Model chat" bên dưới
```

Backend đọc `.env` **gần nhất tính từ `backend/app/` ngược lên**: `backend/.env`
thắng `.env` ở gốc repo. Sửa config → sửa `backend/.env`.

### 2. Backend

```bash
cd backend
uv venv --python 3.13          # hoặc: python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Sinh dataset (~60 sản phẩm) — script gọi OpenRouter
python scripts/generate_dataset.py

# Build embeddings — cache xuống data/embeddings.npy
python scripts/build_embeddings.py

# Chạy server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server log ra danh sách model reachable từ `/v1/models?supported_parameters=tools`.

### 3. Frontend (terminal khác)

```bash
cd frontend
npm install
npm run dev
```

Mở http://localhost:5173 (chat khách) hoặc http://localhost:5173/admin (đăng nhập với `ADMIN_TOKEN` từ `.env`).

## Luồng demo

1. **Chat khách** (`/`): hỏi "tìm váy công sở size M dưới 1 triệu" → LLM gọi `search_products` → hiển thị product card.
2. **Trang admin** (`/admin`):
   - Login với token trong `.env`.
   - Tab **Dashboard**: thấy 4 chỉ số + top sản phẩm.
   - Tab **Sản phẩm**: CRUD. Sau khi sửa → bấm **Rebuild index** (Dashboard).

## Kiểm thử tự động

Bộ test 3 tầng — 54 unit/integration (offline, không cần API key) + 21 system (OpenRouter thật):

```bash
./scripts/run-tests.sh              # lint + unit + integration + FE test (~10s)
./scripts/run-tests.sh --system     # thêm system test với LLM thật (~2 phút)

# lẻ từng phần:
cd backend  && .venv/bin/python -m pytest -q            # unit + integration
cd backend  && .venv/bin/python -m pytest tests/system -m system -q   # system (cần key)
cd frontend && npm test                                 # vitest (React components/hooks)

./scripts/smoke-test.sh             # smoke 1 backend đang chạy (BACKEND_URL=... mặc định :8000)
```

CI/CD (GitHub Actions): `.github/workflows/ci.yml` (mỗi push/PR), `nightly-system.yml`
(08:00 UTC hằng ngày — phát hiện model free bị gỡ/rate-limit), `deploy.yml` (tag `v*`:
docker build → smoke trong container → push GHCR → deploy self-hosted).

Chạy production một origin (API + static FE, không CORS): `docker compose up`.


## Model chat

`CHAT_MODEL` phải nằm trong danh sách model **còn sống** của OpenRouter, nếu không
mọi request chat trả 502. Free model bị gỡ/xoá thường xuyên (`:free` → thu phí, hoặc
bị gỡ hẳn khỏi catalog). Kiểm tra trước khi chat:

```bash
curl -s localhost:8000/api/models | python3 -c \
  "import json,sys; print('\n'.join(m['id'] for m in json.load(sys.stdin)['models']))"
```

Server chỉ **warn** lúc boot nếu `CHAT_MODEL` không reachable — vẫn khởi động được,
lỗi chỉ lộ ra khi chat. Đổi model → sửa `backend/.env` rồi restart.

Model free đang hoạt động (đã verify có hỗ trợ tools, 2026-10):
`inclusionai/ling-3.1-flash`, `nvidia/nemotron-3-super-120b-a12b:free`,
`google/gemma-4-31b-it:free`, `openrouter/free` (router → tự map sang free khả dụng).
Rate-limit 429 là chuyện thường với free — code đã retry sẵn.

## Nâng cấp dễ (đã tách module)

- **Persistence**: thay `backend/app/session.py` in-memory bằng SQLite-backed cùng interface.
- **Embeddings local**: nếu OpenRouter model không khả dụng, code tự fallback `sentence-transformers/all-MiniLM-L6-v2` (cần `pip install sentence-transformers`).
- **Model khác**: đổi `CHAT_MODEL` trong `.env`, không sửa code.