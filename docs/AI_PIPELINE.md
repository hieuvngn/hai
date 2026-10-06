# Pipeline AI — RAG + Function Calling

Tài liệu mô tả **pipeline xử lý yêu cầu chat** của Fashion Sales Chatbot: từ tin nhắn của khách đến câu trả lời cuối cùng. Trọng tâm là hai thuật toán cốt lõi — **RAG** và **Function Calling** — đồng thời bỏ qua toàn bộ phần sinh dữ liệu (`generate_dataset.py`), vì đó là bước chuẩn bị đầu vào một lần, không phải logic runtime.

> Phạm vi: `backend/app/` — `rag/`, `tools/`, `routes/chat.py`, `llm.py`, `prompts/`.
> Thuật ngữ dùng theo `CONTEXT.md` (Sản phẩm, Catalog, Chỉ mục RAG, Công cụ, Phiên tư vấn).

---

## 1. Tổng quan kiến trúc

Hệ thống **không có bước "đưa context vào prompt" thủ công**. Thay vào đó, LLM tự quyết định lúc nào cần dữ liệu, rồi gọi công cụ để lấy. Đây là điểm khác biệt so với RAG kiểu cổ điển (luôn ép top-k vào context).

```
Khách (React)
    │  POST /api/chat  {session_id, message, cart_id, cart_token}
    ▼
┌─────────────────────────────────────────────────────────────┐
│ routes/chat.py — vòng lặp điều phối (tối đa 5 lượt)         │
│                                                             │
│  ① LLM ← messages + tools(CUSTOMER_TOOLS), tool_choice=auto │
│  ② LLM trả tool_calls?  ── không ──▶ trả reply cho client  │
│        │ có                                              │
│        ▼                                                   │
│  ③ DISPATCH[name](args, ctx) → handlers.py                  │
│        │        └─ search_products gọi Embedder + cosine   │
│        ▼                                                   │
│  ④ gói kết quả thành message role="tool" → vòng ①         │
└─────────────────────────────────────────────────────────────┘
    │                    ▲
    ▼                    │ toàn bộ mô hình về 1 provider
OpenRouter API           │
  /v1/chat/completions ─┘   (chat model: qwen/qwen3.8-27b:free)
  /v1/embeddings      ────   (embed: nvidia/llama-nemotron-embed-vl-1b-v2:free)
```

**Điểm cần nhấn mạnh:** mỗi lượt khách chat là *một* HTTP request vào `/api/chat`, nhưng bên trong có thể gọi OpenRouter **nhiều lần**. Ba lượt tool-calling liên tiếp = bốn lần gọi mạng tuần tự. Đây là hệ quả trực tiếp của kiến trúc ReAct, và là nơi cần tối ưu nếu muốn giảm độ trễ.

Phiên tư vấn được giữ trong RAM (`session.py`) với TTL 30 phút, có `sweeper_loop` quét mỗi 60 giây.

---

## 2. Điểm sáng 1 — RAG (Retrieval-Augmented Generation)

### 2.1 Vì sao cần RAG

Mô hình chat **không được biết** catalog. Nếu phó mặc cho nó trả lời tự do, nó sẽ bịa giá và tồn kho — sai hoàn toàn với thực tế bán hàng. RAG giải quyết bằng cách: **chỉ cho phép model phát biểu dữ kiện nào nó đã lấy được qua tool.**

Nguyên tắc 1 trong `prompts/system_customer.txt`:

> CHỈ tư vấn dựa trên catalog. Không bao giờ bịa sản phẩm, giá, size hay tồn kho ngoài dữ liệu tool trả về.

### 2.2 Thuật toán: biến mỗi Sản phẩm thành một vector

Mỗi Sản phẩm được đưa qua một bước **làm phẳng có nhãn** — gộp các trường văn bản thành đúng một chuỗi để nhúng (`schemas.py:28`):

Ví dụ chuỗi thực tế cho một Sản phẩm trong catalog:

```
Tên: Váy linen midi Sunset Denim màu vàng mustard
Thương hiệu: Sunset Denim
Danh mục: váy
Mô tả: Váy midi thiết kế đơn giản với đường cắt xòe nhẹ, làm từ chất liệu linen
       cao cấp mềm mại và thoáng khí, phù hợp cho những ngày hè nóng bức...
Chất liệu: linen
Màu sắc: vàng mustard
Size có sẵn: M, L
Từ khoá: mùa hè, công sở, dạo phố, linen, midi, basic, vàng mustard, thanh lịch
Tồn kho: M:12, L:8
Giới tính: nữ
```


Ba lựa chọn thiết kế đáng chú ý ở đây:

- **Có nhãn tiếng Việt trước mỗi trường** — giúp mô hình embedding hiểu đâu là tên, đâu là chất liệu, thay vì phải đoán từ chuỗi nối liền.
- **Nhúng cả tồn kho và size** — giúp truy vấn "váy size M còn hàng" khớp theo ngữ nghĩa, không phụ thuộc hoàn toàn vào filter.
- **Văn bản tiếng Việt đi nguyên** — không dịch. Embedding đa ngữ giữ được quan hệ ngữ nghĩa; dịch sang tiếng Anh rồi query tiếng Việt sẽ lệch miền.

Script `scripts/build_embeddings.py` chạy **offline một lần**, ghi ra `data/embeddings.npy`. Kết quả thực tế của catalog hiện tại:

```
embeddings shape = (53, 2048)  dtype=float32
```

Chỉ mục nạp lúc khởi động (`rag/index.py`) và nằm nguyên trong RAM suốt vòng đời process. `RagIndex` giữ ba thứ:

| Trường | Kiểu | Vai trò |
|---|---|---|
| `products` | `List[Product]` | Danh sách Sản phẩm, thứ tự khớp hàng |
| `embeddings` | `np.ndarray (N, D)` | Ma trận vector |
| `by_id` | `Dict[str, int]` | `product_id → chỉ số hàng`, tra cứu O(1) |

`load()` kiểm tra `embeddings.shape[0] == len(products)` và **ném lỗi** nếu lệch — chặn trường hợp chỉ mục cũ chạy với catalog mới, một lỗi âm thầm rất dễ xảy ra sau khi admin sửa sản phẩm.

### 2.3 Thuật toán: cosine similarity + lọc cứng

Đây là trái tim của RAG trong dự án (`rag/retriever.py:19`):

$$\text{sim}(q, p_i) = \frac{E \cdot q}{\|E_i\| \cdot \|q\|}$$

Triển khai bằng NumPy vector hoá toàn bộ:

```python
a_norm = np.linalg.norm(index.embeddings, axis=1, keepdims=True)
q_norm = np.linalg.norm(q)
sims = (index.embeddings @ q.T).flatten() / (a_norm.flatten() * q_norm)
```

Ba điểm về thuật toán:

1. **`@` là phép nhân ma trận–vectơ.** Thay vì lặp N sản phẩm, một phép nhân `(53, 2048) @ (2048,)` trả về vector 53 điểm tương đồng. Chi phí là $O(N \cdot D)$ nhưng chạy hoàn toàn trong BLAS.
2. **Chuẩn hoá được tính sẵn một lần cho cả index** (`a_norm`), chỉ `q_norm` tính lại mỗi truy vấn.
3. **Chống chia 0 bằng `np.where(norm == 0, 1e-9, norm)`.** Không có bước này thì một vector 0 (sản phẩm mới chưa embed) sẽ cho `NaN` và làm hỏng cả lượt truy vấn.

Sau khi có `sims`, hệ thống áp **bộ lọc cứng** rồi mới xếp hạng:

| Filter | Điều kiện giữ lại | Ghi chú |
|---|---|---|
| `category` | `p.category == category` | so khớp tuyệt đối |
| `max_price` | `p.price_vnd <= max_price` | |
| `size` | `size in p.sizes_available` | |
| `gender` | `p.gender in (gender, "unisex")` | `unisex` luôn hợp lệ |
| `color` | `color.lower() in {c.lower()}` | so khớp tuyệt đối |

**Đây là kiến trúc "lọc sau, xếp hạng trước" (post-filtering).** Toàn bộ 53 sản phẩm đều được chấm điểm, rồi mới loại. Ưu điểm: `top_k` luôn đầy đủ — không bao giờ trả về 3 kết quả dù chỉ còn 1 sản phẩm thoả ràng buộc. Cái giá phải trả: nếu chỉ 2 sản phẩm dưới 200k mà có 50 sản phẩm trong catalog, ta vẫn chấm điểm cả 50.

Với quy mô này thì vô hại. **Nếu catalog lên tới hàng chục nghìn**, post-filtering sẽ là điểm nghẽn và cần chuyển sang pre-filtering (lọc theo index trước) hoặc ANN index (FAISS/HNSW).

**Kết quả đo thực tế** trên catalog hiện tại:

```
self-retrieval top1:  P0001, cosine = 1.000    (đúng sản phẩm truy vấn)
top3:  Áo sơ mi lụa Phố Studio   1.000
       Áo sơ mi nữ Mây Boutique  0.736
       Áo sơ mi Đóa cổ V dài     0.628

max_price=500k  → 25 kết quả, giá cao nhất 490.000 ✓
size="XL"       → 15 kết quả, tất cả đều có XL ✓
gender="nữ"    → 43 kết quả, tất cả nữ/unisex ✓

100 truy vấn: 9.5 ms  →  0.09 ms/truy vấn
```

Vài kết quả đáng chú ý về mặt chất lượng:

- **Self-retrieval đạt cosine = 1.000 chính xác** — chứng minh pipeline embed → index → truy vấn là nhất quán, không lệch chiều hay lỗi chuẩn hoá.
- **Ba sản phẩm khác nhau truy vấn đều trả về chính nó ở top-1 với score 1.000**, xác nhận tính ổn định của phép tính.
- **Các sản phẩm "áo" xếp cạnh nhau theo ngữ nghĩa** (sơ mi ↔ sơ mi ↔ blouse) chứ không ngẫu nhiên — mô hình embedding nắm được quan hệ tương đồng trong ngành thời trang tiếng Việt.

### 2.4 Tư vấn theo giỏ hàng — mở rộng của RAG

`recommend_similar` (`tools/handlers.py:154`) mở rộng ý tưởng truy vấn theo giỏ hàng, với hai chế độ:

- **`similar`** — cùng `category`, loại trừ chính sản phẩm đang xét và các mục đã có trong giỏ.
- **`complement`** — `category` khác, theo bảng ánh xạ nghiệp vụ (`COMPLEMENT_MAP`):

```python
"váy":  ["áo", "phụ kiện", "giày"]
"áo":   ["quần", "váy", "phụ kiện"]
"quần": ["áo", "giày", "phụ kiện"]
...
```

Thuật toán, theo thứ tự:

1. Với **từng** mục giỏ, tính `sims` của nó với toàn bộ index.
2. Lọc theo ràng buộc `category` của chế độ đang chạy.
3. Lấy `top_k` ứng viên **cho từng mục giỏ**.
4. **Gộp toàn cục theo `product_id`, giữ điểm cao nhất** (`if p.id not in scored or scored[p.id].score < score`).
5. Sắp xếp lại toàn bộ và cắt `top_k`.

Bước 4 là chi tiết đáng chú ý: nếu một sản phẩm được nhiều mục giỏ "chỉ tới", nó có thể xuất hiện nhiều lần ở bước 3. Việc gộp theo điểm tối đa giữ cho mỗi sản phẩm xuất hiện đúng một lần — đây là cơ chế **dedupe giữ điểm max**.

Về mặt đặt tên, dự án cố tình tránh gọi đây là "AI recommendation" hay "cá nhân hoá". `CONTEXT.md` định nghĩa nó là **context-aware retrieval có cấu trúc**: tín hiệu đầu vào là Giỏ hàng (dữ kiện có cấu trúc, đã biết `product_id` và `size`), không phải lịch sử chat (văn bản tự do, không parse được). Gọi đúng tên giúp tránh hứa hẹn vượt quá khả năng thật.

---

## 3. Điểm sáng 2 — Function Calling

### 3.1 Vấn đề cần giải

LLM chỉ tạo ra **văn bản**. Muốn nó tra cứu tồn kho thật, phải có cầu nối giữa ý định của model và hàm Python thật. Function calling là cầu nối đó: server gửi kèm **JSON Schema** mô tả các hàm khả dụng, model trả về tên hàm + tham số dạng JSON, server thực thi và trả kết quả lại cho model.

Trong dự án này, Function Calling không chỉ là chi tiết kỹ thuật — nó là **cơ chế kiểm soát luồng nghiệp vụ**. Mọi hành động thay đổi dữ liệu đều phải đi qua nó.

### 3.2 Thuật toán: vòng lặp điều phối

Phần cốt lõi nằm ở `routes/chat.py:57`:

```python
for _ in range(5):                              # chặn vòng lặp vô hạn
    resp = await chat_completion(
        messages=messages_for_llm,
        tools=CUSTOMER_TOOLS,
        tool_choice="auto",
    )
    msg = resp["choices"][0]["message"]
    tool_calls = msg.get("tool_calls") or []

    if not tool_calls:                          # ← điểm thoát
        return ChatResponse(reply=msg["content"], ...)

    messages_for_llm.append(msg)
    for tc in tool_calls:
        handler = DISPATCH.get(tc["function"]["name"])
        targs = json.loads(tc["function"]["arguments"])
        tr = await handler(targs, ctx)
        messages_for_llm.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": json.dumps(tr.llm_payload, ensure_ascii=False),
        })
```

Các quyết định thuật toán đáng phân tích:

**a) `tool_choice="auto"`** — model tự quyết định có gọi hay không. Rẻ hơn `required`, nhưng phụ thuộc vào chất lượng system prompt. Đây chính là lý do ADR-0006 ghi lại một bài học đắt giá:

> Việc prompt chỉ liệt kê 4 tool chỉ-đọc là một lỗi đã gặp: model chỉ gọi được những gì prompt dạy, nên 4 tool thương mại dù đăng ký đầy đủ vào `tool_choice` vẫn không bao giờ được gọi.

**b) Giới hạn 5 lượt** — trần cứng chống vòng lặp vô hạn khi model mắc kẹt gọi lại cùng một tool. Hết 5 lượt thì trả HTTP 500. Với quy trình đặt hàng dài nhất (`check_stock` → `add_to_cart` → `update_customer_profile` → `create_order`) vẫn còn dư 1 lượt, nên tham số này có biên an toàn thực tế.

**c) `ToolResult` mang hai kênh thông tin.** Đây là thiết kế hay nhất trong phần này:

```python
@dataclass
class ToolResult:
    llm_payload: Dict[str, Any]   # dữ liệu để LLM đọc
    products:    List[Product]    # để frontend render product card
```

`search_products` trả về 8 trường cho LLM (id, tên, giá, size…) nhưng gửi **đủ `Product` cho giao diện**. Nhờ vậy LLM không phải "diễn giải" kết quả thành thẻ sản phẩm HTML, mà UI vẫn hiển thị card đầy đủ. Việc tách này giải quyết trực tiếp hạn chế cố hữu của function calling: **model giỏi chọn tool hơn giỏi trình bày kết quả**.

**d) Tool lỗi không được làm sập lượt** (`chat.py:103`):

```python
except Exception as e:
    tr = ToolResult(llm_payload={"error": f"tool '{tname}' lỗi: {e}"}, products=[])
```

Args do LLM sinh ra nên thiếu/sai kiểu là chuyện thường. Thay vì trả 500 cho khách, lỗi được đóng gói thành JSON và đưa ngược lại cho model — nó đọc lỗi rồi tự sửa và gọi lại. Đây là mẫu xử lý lỗi đúng cho hệ thống dựa trên LLM: **lỗi là dữ liệu, không phải sự cố**.

**e) Chống đếm trùng dashboard** (`chat.py:110`): chỉ truyền `call_products` của đúng tool-call hiện tại vào `track_tool_call`, không truyền cả `products_this_turn` đang tích luỹ — tránh đếm lặp mỗi sản phẩm khi có nhiều tool trong một lượt.

### 3.3 Bảng công cụ

| Công cụ | Tham số | Tác dụng |
|---|---|---|
| `search_products` | `query`, `category?`, `size?`, `max_price?`, `color?`, `gender?` | RAG + lọc cứng |
| `get_product` | `product_id` | Chi tiết đầy đủ |
| `check_stock` | `product_id`, `size?` | Tồn kho theo size |
| `recommend_similar` | `mode?` (`similar`/`complement`), `k?` | Tư vấn theo giỏ |
| `add_to_cart` | `product_id`, `size`, `quantity?` | Thêm vào giỏ |
| `get_cart` | — | Nội dung giỏ |
| `update_customer_profile` | `phone`, `name`, `address` | Lưu thông tin giao hàng |
| `create_order` | `phone` | Tạo đơn từ giỏ |

Phân tách ranh giới quyền hạn được ghi trong ADR-0003:

- **Khách** → chỉ-đọc trên catalog. Tất cả thao tác ghi (`add_to_cart`, `create_order`) đều gắn với `cart_token` do server kiểm tra, không phải tham số LLM gửi lên.
- **Admin** → CRUD qua REST trực tiếp, **không qua LLM**. Lý do: form REST có validation rõ ràng và xác thực token, đáng tin hơn việc để LLM tự quyết định sửa dữ liệu.
- **Ngoại lệ duy nhất** (ADR-0008): `create_order` do LLM gọi, vì Order là kết quả của cả cuộc tư vấn — bắt khách rời chat sang điền form sẽ phá vỡ UX mua hàng.

### 3.4 Ràng buộc nghiệp vụ nhúng thẳng vào prompt

Điểm mạnh nhất của thiết kế này: quy trình nghiệp vụ **không nằm trong code**, mà nằm trong `prompts/system_customer.txt`:

```
1. check_stock xác nhận còn hàng đúng size → add_to_cart
2. Thiếu thông tin giao hàng → hỏi khách → update_customer_profile
3. Sau khi update_customer_profile thành công → TUYỆT ĐỐI không hỏi lại
4. Khách xác nhận mua → create_order, gọi ngay lượt này
5. Nếu create_order trả lỗi → xử lý đúng lỗi đó
```

Bước 3 là ví dụ điển hình của *prompt engineering dựa trên hành vi quan sát được*: ADR-0006 ghi rõ model free hay hỏi lại tên/SĐT ở mọi lượt và vì thế **không bao giờ chạm tới `create_order`**. Chỉ một câu ràng buộc đã sửa được hẳn một nhánh nghiệp vụ.

### 3.5 Độ bền trước lỗi hạ tầng

`llm.py` phân loại lỗi thành hai nhóm để quyết định có retry hay không:

| Lớp lỗi | Nguyên nhân | Xử lý |
|---|---|---|
| `TransientError` | HTTP 429, 5xx, timeout, network, "rate limit"/"overloaded" trong message | `tenacity` retry |
| `FatalError` | 401, 400, model không tồn tại | ném ngay, không retry |

Tham số retry (`_retry_kwargs`): tối đa 3 lần, chờ luỹ thừa `multiplier=2`, kẹp trong `[2s, 10s]` → **2s → 4s → 8s**.

Không retry lỗi fatal là quan trọng: một API key sai sẽ thử 3 lần rồi vẫn fail, chỉ là chậm thêm 6 giây. Ngược lại, 429 trên free tier rất phổ biến và retry là chính sách đúng.

**Quan sát thực tế:** khi chạy thử với model free, log ghi nhận đúng tình huống này:

```
WARNING | app.llm:chat_completion:96 - Chat upstream 429/overload:
  'qwen/qwen3.8-27b:free is temporarily rate-limited upstream'
```

Lượt gọi vẫn hoàn tất thành công sau 90.6 giây nhờ retry. Đây là bằng chứng cơ chế backoff hoạt động đúng trong điều kiện vận hành thật — cũng là lý do thời gian phản hồi có độ trễ lớn không ổn định: độ trễ phụ thuộc mức rate-limit của nhà cung cấp, không chỉ phụ thuộc hệ thống.

Ngoài ra `warmup_or_die()` kiểm tra key và danh sách model lúc khởi động để fail-fast, `Embedder` tự chuyển sang `sentence-transformers/all-MiniLM-L6-v2` cục bộ nếu model embedding không khả dụng (ADR-0002).

---

## 4. Đánh giá tổng hợp

### Điểm mạnh

| Điểm | Bằng chứng |
|---|---|
| RAG chạy đúng và nhanh | Self-retrieval cosine = 1.000; 0.09 ms/truy vấn |
| Bộ lọc cứng tôn trọng ràng buộc | `max_price`, `size`, `gender` kiểm bằng dữ liệu thật: 25 kết quả ≤ 490k, 15 kết quả đều có XL, 43 kết quả đều nữ/unisex |
| Chống ảo giác có cơ chế | Nguyên tắc 1 trong prompt + `TestRagRetrieval` khẳng định mọi sản phẩm trả về phải có trong catalog |
| Tool lỗi không làm sập lượt | Lỗi đóng gói JSON trả lại cho model tự sửa |
| Retry đúng phân loại lỗi | Ghi nhận 429 upstream, vẫn trả kết quả sau 90.6s |
| Kiểm tra lệch chỉ mục | `RagIndex.load()` ném lỗi khi số hàng không khớp catalog |

### Hạn chế đã xác minh

Các mục dưới đây **đã kiểm chứng bằng chạy thật**, không phải suy đoán:

**1. Filter màu sắc dùng so khớp tuyệt đối — không khớp với màu nhiều từ.**

```python
colors_lower = {c.lower() for c in p.colors}
if color.lower() not in colors_lower: continue    # rag/retriever.py:52
```

Màu thật trong catalog: `đỏ đô`, `xanh navy`, `nâu đất`, `vàng mustard`… Khi LLM truyền `color="đỏ"` (tên màu phổ biến, khách cũng hay nói vậy) thì:

```
color='Đỏ' → 0 kết quả   (giá trị 'đỏ' không tồn tại trong catalog)
```

Khách hỏi "áo đỏ" sẽ nhận về danh sách rỗng dù catalog có 6 sản phẩm `đỏ đô`. Nguyên nhân gốc: **cùng một màu được lưu ở nhiều dạng khác nhau trong dữ liệu**, còn bộ lọc lại chỉ so khớp chuỗi. Hướng sửa: lưu màu dạng chuẩn hoá (`đỏ`, `xanh navy`) và so khớp tiền tố, hoặc dùng danh sách màu hợp lệ trong `enum` của JSON Schema để buộc LLM chọn đúng giá trị có sẵn.

**2. JSON Schema không chặn được LLM sinh khoá sai — bộ lọc bị bỏ qua âm thầm.**

Quan sát trực tiếp từ lời gọi thật với model `qwen/qwen3.8-27b:free`:

```json
{"query":"váy công sở","category":"váy","gender":"nữ","size-":"M","max_price-":"1000000"}
```

Chú ý `size-` và `max_price-` — có dấu gạch ngang thừa. `json.loads` vẫn parse thành công (đây là JSON hợp lệ), nhưng handler đọc bằng `args.get("max_price")` nên **nhận về `None`** và bỏ qua cả hai ràng buộc:

| | Kết quả | Đúng kỳ vọng? |
|---|---|---|
| Args đúng khoá | 1 sản phẩm, đều ≤ 1tr và có size M | ✓ |
| Args có `size-`/`max_price-` | 5 sản phẩm, **có món 1.250.000**, thiếu size M | ✗ |

Không có lỗi nào được nêu ra — hệ thống im lặng bỏ qua ràng buộc của khách và trả về sản phẩm quá ngân sách. Đây là rủi ro thực tế với mô hình free, không phải lý thuyết. Hướng sửa: xác thực args bằng Pydantic **trước** khi chạy filter, hoặc chuẩn hoá khoá (bỏ ký tự lạ) khi parse.

**3. `similar_to_product` không được dùng trong production.**

`rag/retriever.py` định nghĩa hàm này và có unit test riêng, nhưng `handle_recommend_similar` tự cài đặt lại thuật toán tương đương tại `handlers.py:186-241` (bao gồm cả logic `complement` mà hàm gốc không có). Hàm gốc chỉ được gọi từ test. Nên dọn hoặc gộp để tránh hai đường triển khai cùng thuật toán dễ lệch nhau.

### Điểm mở rộng

| Hướng | Chi tiết |
|---|---|
| Pre-filtering | Khi catalog > vài chục nghìn, chuyển lọc trước / dùng FAISS-HNSW thay cho quét toàn bộ |
| Gộp vector + BM25 | Vector bắt nghĩa, từ khóa bắt tên riêng ("Maison Étoile") mà RAG thuần hay bỏ sót |
| Cache truy vấn | Cùng câu hỏi lặp lại → cache theo chuẩn hoá query, giảm tải free tier đang bị rate-limit |
| Parallel tool calls | Model trả nhiều `tool_calls` trong một lượt hiện được xử lý tuần tự; chạy song song sẽ cắt độ trễ |

---

## 5. Cách kiểm chứng lại

```bash
cd backend

# RAG offline — không cần API key
.venv/bin/python -m pytest tests/test_rag_retriever.py -q

# Toàn bộ unit + integration
.venv/bin/python -m pytest -q

# System test với LLM thật (cần OPENROUTER_API_KEY)
.venv/bin/python -m pytest tests/system -m system -q
```

System test khẳng định vào **bất biến hệ thống** chứ không so lời thoại, vì mô hình free có tính xác suất: đúng là tool có được gọi, kết quả có nằm trong catalog thật, ràng buộc lọc có được tôn trọng.