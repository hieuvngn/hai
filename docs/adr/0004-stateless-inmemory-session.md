# ADR-0004: Session store in-memory với TTL, thiết kế module để swap SQLite

**Status**: accepted

Lưu phiên trong dict `Dict[str, SessionRecord]` trong RAM, có background task dọn session `last_seen > 30 phút`. Mỗi `SessionRecord` chứa `messages`, `tool_calls`, `products_consulted` (Set đếm tần suất cho dashboard). Lý do: đồ án, dataset nhỏ, không cần persistence qua restart. Mất khi restart server.

Code trong module `backend/app/session.py` chỉ expose interface `get/put/append/track_product/sweep_expired`. Khi cần persistence, thay implementation bằng SQLite-backed mà không sửa router.

**Consequences**:
- Restart server → mất toàn bộ phiên đang hoạt động và thống kê dashboard.
- Đồng hồ đếm `products_consulted` chỉ đúng trong vòng đời server hiện tại.