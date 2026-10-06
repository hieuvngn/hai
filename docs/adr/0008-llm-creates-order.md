# ADR-0008: Ngoại lệ ADR-0003 — LLM được tạo Order qua tool

**Status**: accepted

ADR-0003 quy định "CRUD = REST form, khách chỉ-đọc qua tool". Order là ngoại lệ: LLM gọi tool `create_order(cart_id)` khi khách xác nhận mua trong chat. CRUD sản phẩm vẫn qua REST form như cũ.

Lý do là ngoại lệ: Order là kết quả của cuộc tư vấn — khách đã chọn được sản phẩm qua nhiều lượt hội thoại, LLM đã gọi `search_products` + `check_stock` + `recommend_similar` để thuyết phục. Bắt khách rời chat, mở form `/admin`, điền cart_id thủ công → phá UX mua hàng. Order qua REST form chỉ khả thi nếu admin tạo đơn từ yêu cầu khách ngoài chat, không phải luồng này.

Cơ chế an toàn thay cho "admin bấm nút":
- Server-side tool handler lấy cart từ `cart_id`, **re-verify tồn kho** tại thời điểm tạo Order (không tin stock client đã cache).
- Khách phải có `CustomerProfile` (theo ADR-0009) với `phone`, `address` trước khi tạo Order; nếu thiếu, LLM phải hỏi trước.
- Order chỉ chuyển sang `confirmed` khi admin duyệt qua `POST /api/admin/orders/{id}/confirm` — LLM không có quyền confirm. Mặc định tạo ra ở state `pending`.

**Chính sách giá tại `create_order`:** Khách add-to-cart lúc giá X. Nếu admin đổi catalog giá Y ≠ X trước khi khách confirm, Order vẫn ghi `price_vnd_snapshot = X` (giá tại lúc thêm vào giỏ). Admin chịu phần chênh `Y - X` nếu `Y > X`, hưởng phần chênh nếu `Y < X`. Đây là đánh đổi chấp nhận được cho đồ án: admin có thể tự điều chỉnh bằng cách cập nhật giá sau khi hết cart cũ, hoặc tự liên hệ khách.

**Thống kê cho admin:** Mỗi Order lưu `price_vnd_snapshot` (giá khách đặt) và snapshot tên + image. Dashboard có thêm ô thứ 5: **"Số đơn có giá chênh catalog hiện tại"** — đếm order ở trạng thái `pending` hoặc `confirmed` có `price_vnd_snapshot ≠ products.price_vnd`. Tab **Orders** riêng (`/admin/orders`) liệt kê toàn bộ + filter "chỉ đơn có giá chênh".

6 state: `pending → confirmed → shipped → completed`, nhánh `cancelled` (khách đổi ý, admin kích hoạt) và `failed` (giao hàng không thành công, admin kích hoạt).