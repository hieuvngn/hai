# ADR-0009: Recommendation theo Cart + CustomerProfile bán ẩn danh

**Status**: accepted

Hai quyết định:

**1. `recommend_similar` đọc Cart, có 2 mode:**
- `recommend_similar(cart_id, mode="similar", k=3)` — tìm sản phẩm tương tự từng item trong cart (cùng category, embedding gần). Dùng cho UI "Xem thêm sản phẩm tương tự".
- `recommend_similar(cart_id, mode="complement", k=3)` — tìm sản phẩm category khác, hay đi kèm (cart có váy → gợi ý áo/blazer/phụ kiện). Dùng cho UI "Complete the look".

Cả hai đều query `GET /api/cart/{cart_id}` nội bộ (qua `cart_token` server-side, không lộ cho LLM), lấy items hiện tại làm query seed. Lý do dùng Cart làm signal chứ không dùng lịch sử chat: Cart là dữ kiện có cấu trúc (đã biết product_id, size), lịch sử chat thì không. "Cá nhân hoá trong 30 phút" thực ra là context-aware retrieval — mình đổi tên thành **Tư vấn theo giỏ hàng** trong `CONTEXT.md` cho trung thực.

**2. CustomerProfile — khách "bán ẩn danh":**
- Khách không cần email/password, nhưng cần `phone` (identity) + `name` + `address` để giao hàng.
- `phone` là khoá tự nhiên; nếu khách dùng lại SĐT ở session khác, server liên kết cùng `CustomerProfile` (qua cache localStorage + lookup theo phone khi session bắt đầu).
- Profile persist qua nhiều phiên, TTL 90 ngày không hoạt động.
- Định nghĩa "Khách" trong `CONTEXT.md` đổi từ "ẩn danh" thành **"bán ẩn danh"** — sửa ngay khi ADR này accepted.