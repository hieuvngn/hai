# ADR-0007: Giỏ hàng persistent với REST API + cart_token

**Status**: accepted

Giỏ hàng (`Cart`) là entity riêng, sống qua nhiều `Phiên tư vấn` (vượt TTL 30 phút). Server sinh `cart_id` khi khách thao tác giỏ lần đầu qua `POST /api/cart`. Mỗi `cart_id` đi kèm `cart_token` (random secret) trả về một lần; client lưu localStorage, gửi header `X-Cart-Token` cho mọi request cart. Server stateless về session — chỉ stateful về cart.

Lý do tách Cart khỏi `SessionRecord`: khách có thể thêm vào giỏ rồi đóng tab, mở lại ngày hôm sau. `SessionRecord` expire 30 phút (ADR-0004) là quá ngắn cho mua sắm thời trang. Lý do cần `cart_token` thay vì tin `cart_id` thuần: cart chứa items kèm giá, ai giữ `cart_id` có thể sửa cart của người khác nếu guess được UUID — `cart_token` 256-bit ngẫu nhiên làm bearer credential, không cần login.

REST endpoints:
- `POST /api/cart` → `{cart_id, cart_token}`. Tạo cart rỗng.
- `GET /api/cart/{cart_id}` (header `X-Cart-Token`) → trả items.
- `POST /api/cart/{cart_id}/items` (header) → thêm `{product_id, size, quantity}`. Server lookup `Sản phẩm`, verify `stock_per_size[size] >= quantity`, gắn giá hiện tại (snapshot, không trust client).
- `PUT /api/cart/{cart_id}/items/{product_id}/{size}` (header) → đổi quantity.
- `DELETE /api/cart/{cart_id}/items/{product_id}/{size}` (header) → xoá.
- Không có endpoint "xem cart của user khác" — không có user.

Storage: cùng pattern với `products.jsonl` (in-memory load từ file, persist sau mỗi mutation). TTL cart: 7 ngày không hoạt động, cleanup background task.