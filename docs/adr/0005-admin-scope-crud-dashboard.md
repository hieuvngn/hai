# ADR-0005: Phạm vi admin — Dashboard 4 chỉ số + CRUD sản phẩm

**Status**: accepted

Trang `/admin` có 2 phần:

**Dashboard** (5 chỉ số, không biểu đồ):
- Tổng số sản phẩm (đếm `products.jsonl`).
- Số phiên đang hoạt động (đếm session chưa expire).
- Số khách (số `session_id` đã thấy kể từ khi server khởi động).
- Top 5 sản phẩm được tư vấn nhiều nhất (sort `products_consulted` counter giảm dần).
- Số đơn hàng có giá chênh catalog hiện tại (xem ADR-0008).

**Quản lý sản phẩm**: bảng liệt kê + form thêm/sửa + nút xoá + nút "Rebuild index".

**Quản lý đơn hàng** (tab riêng `/admin/orders`): bảng tất cả Order, filter "chỉ đơn có giá chênh", hành động `confirm` / `ship` / `complete` / `cancel` / `fail` chuyển `Trạng thái đơn hàng` (xem ADR-0008).

Lý do không biểu đồ: đồ án, không tốn thời gian vẽ chart khi 4 con số đã đủ demo. Lý do không auth đầy đủ: chỉ cần 1 admin, demo trong nội bộ.