# ADR-0002: Embedding qua OpenRouter thay vì local

**Status**: accepted

Dùng `nvidia/llama-nemotron-embed-vl-1b-v2:free` qua OpenRouter `/v1/embeddings` thay vì `sentence-transformers` cục bộ. Lý do: thống nhất provider với chat (cùng key, cùng base URL), không tải model ~80–400MB cục bộ. Cache embeddings xuống `data/embeddings.npy` sau lần build đầu để tránh gọi API mỗi request (free tier giới hạn 50–1000 RPD).

**Considered Options**:
- Local `sentence-transformers/all-MiniLM-L6-v2` — miễn phí, nhanh, không tốn RPD, nhưng thêm dependency model lớn vào project.
- OpenRouter `nvidia/llama-nemotron-embed-vl-1b-v2:free` — chọn vì thống nhất provider.

**Consequences**:
- Build embedding lần đầu cần ~60 SP × vài giây gọi API (ước tính 30–60s với rate limit).
- Fallback: nếu model không có trong `GET /v1/embeddings`, code tự chuyển sang local `all-MiniLM-L6-v2` và log cảnh báo.
- Build embeddings bằng script offline `scripts/build_embeddings.py`, không tự động trong runtime. Admin kích hoạt qua nút "Rebuild index" trong dashboard sau khi CRUD.