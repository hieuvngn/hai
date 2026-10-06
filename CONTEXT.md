# Fashion Sales Chatbot — Ngữ cảnh dự án

Chatbot tư vấn bán hàng thời trang dùng RAG (Retrieval-Augmented Generation) + Function Calling, giao tiếp qua OpenRouter API. Backend Python (FastAPI), frontend React + TypeScript (Vite + Tailwind + shadcn/ui).

## Language

**Sản phẩm**:
Một mặt hàng thời trang trong catalog có `id`, `name`, `brand`, `category`, `description`, `price_vnd`, `sizes_available`, `colors`, `material`, `stock_per_size`, `tags`, `image_url`, `gender`.
_Avoid_: item, hàng hoá, SKU

**Catalog**:
Tập hợp tất cả `Sản phẩm` lưu trong `data/products.jsonl` — nguồn dữ liệu duy nhất cho RAG và tra cứu.
_Avoid_: dataset, kho dữ liệu

**Danh mục** (Category):
Một trong sáu nhóm: `áo`, `quần`, `váy`, `giày`, `phụ kiện`, `đồ thể thao`.
_Avoid_: loại, nhóm hàng

**Thương hiệu** (Brand):
Nhãn hiệu giả định gắn trên mỗi `Sản phẩm` (vd "Maison Étoile", "Linh & Co").
_Avoid_: nhãn hàng, hãng

**Index (RAG Index)**:
Vector embeddings của toàn bộ `Sản phẩm`, cache tại `data/embeddings.npy` + metadata tại `data/products.jsonl`. Build một lần bằng script `scripts/build_embeddings.py`, không tự động rebuild runtime.
_Avoid_: vector store, embedding cache

**Công cụ** (Tool):
Một hàm JSON-schema mà LLM có thể gọi qua OpenRouter `tool_choice`. Có hai nhóm: công cụ khách (chỉ-đọc) và công cụ admin (CRUD).
_Avoid_: function, action

**Phiên tư vấn** (Consultation Session):
Một chuỗi hội thoại giữa một khách và chatbot, xác định bằng `session_id` (UUID v4, lưu `localStorage` ở client). Lưu trong RAM theo dict `session_id → SessionRecord`, TTL 30 phút không hoạt động.
_Avoid_: chat session, conversation

**Bản ghi phiên** (Session Record):
Cấu trúc in-memory cho mỗi phiên: `session_id`, `created_at`, `last_seen`, `messages: List[Message]`, `tool_calls: List[ToolCallEvent]`, `products_consulted: Set[str]` (đếm tần suất LLM trả sản phẩm nào cho dashboard).
_Avoid_: chat history, session state

**Khách** (Customer):
Người dùng bán ẩn danh truy cập `/`, hỏi chatbot về sản phẩm. Không cần đăng nhập bằng email/password, nhưng có thể cung cấp `phone` + `name` + `address` để mua hàng (xem `Hồ sơ khách`). `session_id` vẫn ẩn danh — `phone` chỉ liên kết nếu khách chủ động cung cấp.
_Avoid_: user, visitor, end-user

**Hồ sơ khách** (Customer Profile):
Bản ghi lưu `phone` (khoá định danh) + `name` + `address` của một `Khách`, dùng để tạo `Đơn hàng` qua tool `create_order`. Persist qua nhiều `Phiên tư vấn`, TTL 90 ngày không hoạt động. Một `Khách` (xác định bằng `phone`) có thể có nhiều `Phiên tư vấn` và nhiều `Giỏ hàng`.
_Avoid_: user profile, customer account

**Giỏ hàng** (Cart):
Tập `Mục giỏ` mà `Khách` đã chọn nhưng chưa đặt. Persistent qua nhiều `Phiên tư vấn` (sống qua TTL 30 phút của session), TTL 7 ngày không hoạt động. Xác định bằng `cart_id` (UUID), truy cập qua header `X-Cart-Token` (random secret sinh cùng `cart_id`, lưu `localStorage`).
_Avoid_: basket, shopping bag

**Mục giỏ** (Cart Item):
Một dòng trong `Giỏ hàng`: `product_id` + `size` + `quantity` + `price_vnd_snapshot` (giá tại thời điểm thêm, không cập nhật khi catalog đổi). Một `(product_id, size)` xuất hiện tối đa 1 lần trong một `Giỏ hàng`.
_Avoid_: line item, cart entry

**Token giỏ hàng** (Cart Token):
Random secret 256-bit sinh cùng `cart_id`, dùng để xác thực mọi thao tác trên `Giỏ hàng`. Client lưu `localStorage`, gửi header `X-Cart-Token`. Bearer credential — không cần login, không cần `Phiên tư vấn` tương ứng.
_Avoid_: cart password, cart key

**Đơn hàng** (Order):
Một `Đơn hàng` được tạo khi `Khách` xác nhận mua trong chat. LLM gọi tool `create_order(cart_id)` sau khi `Khách` đồng ý (xem ADR-0008). Mỗi `Đơn hàng` snapshot `Mục đơn` từ `Giỏ hàng` tại thời điểm tạo (sau đó sửa `Giỏ hàng` không ảnh hưởng `Đơn hàng`).
_Avoid_: purchase, transaction, invoice

**Mục đơn** (Order Item):
Một dòng trong `Đơn hàng`: `product_id` + `size` + `quantity` + `price_vnd_snapshot` + `name_snapshot` + `image_url_snapshot`. Snapshot đầy đủ vì `Sản phẩm` có thể bị sửa hoặc xoá sau khi `Đơn hàng` tạo.
_Avoid_: order line, order entry

**Trạng thái đơn hàng** (Order Status):
Một trong sáu giá trị: `pending`, `confirmed`, `shipped`, `completed`, `cancelled`, `failed`. Đơn vừa tạo ở `pending`. Admin chuyển `pending → confirmed` qua `POST /api/admin/orders/{id}/confirm`. Khách không chuyển trạng thái.
_Avoid_: order state

**Tư vấn theo giỏ hàng** (Cart-Driven Recommendation):
Gợi ý `Sản phẩm` dựa trên các `Mục giỏ` hiện tại, thay vì lịch sử chat. Tool `recommend_similar(cart_id, mode, k)` có 2 mode: `similar` (cùng category, embedding gần) và `complement` (category khác, hay đi kèm). Không phải "cá nhân hoá" — chỉ là context-aware retrieval có cấu trúc.
_Avoid_: personalization, AI recommendation

**Token phiên admin** (Admin Token):
Chuỗi bí mật cố định trong biến môi trường `ADMIN_TOKEN`, dùng để xác thực admin khi gọi REST `/api/admin/*`.
_Avoid_: admin password, admin key

**Lệnh xây lại chỉ mục** (Rebuild Index):
Hành động chạy lại `scripts/build_embeddings.py` để cập nhật `data/embeddings.npy` sau khi catalog thay đổi. Admin kích hoạt thủ công qua nút trong dashboard, không tự động.
_Avoid_: reindex, refresh embeddings

**Trang tổng quan** (Dashboard):
Trang `/admin` sau khi đăng nhập, hiển thị 4 chỉ số: tổng sản phẩm, số phiên đang hoạt động, tổng khách (số `session_id` từng thấy), top sản phẩm được tư vấn nhiều nhất.
_Avoid_: admin home, control panel

**Mô hình ngôn ngữ** (LLM):
Chat model `inclusionai/ling-3.0-flash-fin:free` qua OpenRouter. LLM nhận `tools` (JSON schema) và `tool_choice="auto"`, quyết định khi nào gọi công cụ nào.
_Avoid_: AI model, GPT

**Mô hình nhúng** (Embedding Model):
Model `nvidia/llama-nemotron-embed-vl-1b-v2:free` qua OpenRouter `/v1/embeddings`, dùng để vector hoá mô tả sản phẩm cho RAG. Có fallback local `sentence-transformers/all-MiniLM-L6-v2` nếu model không có trong catalog OpenRouter.
_Avoid_: encoder, vectorizer

**Khôi phục khi lỗi** (Backoff):
Khi OpenRouter trả 429, client đợi `Retry-After` (hoặc exponential backoff 2→4→8s) rồi thử lại, tối đa 3 lần.
_Avoid_: retry policy