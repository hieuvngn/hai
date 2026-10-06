# ADR-0003: Tool surface chia theo vai — khách chỉ-đọc, admin có CRUD

**Status**: accepted

Công cụ cho LLM chia hai nhóm:

**Khách** (chỉ-đọc):
- `search_products(query, category?, size?, max_price?, color?)` — tìm sản phẩm qua RAG + filter cứng.
- `get_product(product_id)` — lấy chi tiết một sản phẩm.
- `check_stock(product_id, size?)` — kiểm tra tồn kho.
- `recommend_similar(product_id, k=3)` — đề xuất sản phẩm tương tự.

**Admin** (CRUD — gọi qua REST trực tiếp từ form, không qua LLM):
- `POST /api/admin/products` (create)
- `PUT /api/admin/products/{id}` (update)
- `DELETE /api/admin/products/{id}` (delete)
- `POST /api/admin/rebuild-index` (chạy script build_embeddings)
- `GET /api/admin/stats` (dashboard metrics)

Lý do tách: CRUD qua form REST đáng tin cậy và có validation rõ ràng hơn so với LLM tự gọi tool. Công cụ khách chỉ-đọc vì khách ẩn danh không nên có quyền thay đổi dữ liệu.