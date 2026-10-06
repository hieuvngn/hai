# ADR-0006: System prompt cho chatbot khách — bắt buộc tra cứu trước khi báo

**Status**: accepted

System prompt bằng tiếng Việt, gồm 5 nguyên tắc:

1. **Chỉ tư vấn dựa trên catalog** — không được bịa sản phẩm ngoài tool. Nếu tool không trả về kết quả, nói rõ "hiện không có trong danh mục".
2. **Không báo giá/size/stock nếu chưa tra cứu** — bắt buộc gọi `get_product` hoặc `check_stock` trước.
3. **Giọng thân thiện, gợi ý size/màu** — hỏi thêm nếu khách mơ hồ (vd "anh/chị thích size nào?").
4. **Trả lời ngắn gọn + gọi tool khi cần** — `tool_choice: "auto"`, không spam tool khi không cần.
5. **Chỉ tạo đơn khi khách đồng ý** — không tự ý gọi `create_order` khi khách còn đang cân nhắc.

Ngoài 5 nguyên tắc, prompt liệt kê **đủ 8 tool** dưới mục "Khi nào gọi tool" và một mục "Quy trình đặt hàng" hiện thực hoá cơ chế an toàn của ADR-0008: `check_stock` → `add_to_cart` → `update_customer_profile` → `create_order`. Ràng buộc quan trọng nhất: sau khi `update_customer_profile` trả về thành công thì thông tin đã lưu, cấm hỏi lại — thiếu chỗ này mô hình free sẽ hỏi lại tên/SĐT/địa chỉ ở mọi lượt và không bao giờ chạm tới `create_order`.

Việc prompt chỉ liệt kê 4 tool chỉ-đọc là một lỗi đã gặp: model chỉ gọi được những gì prompt dạy, nên 4 tool thương mại dù đăng ký đầy đủ vào `tool_choice` vẫn không bao giờ được gọi. `tests/system/test_sys_purchase.py::test_tc_order_01_full_flow` là hàng rào cho hồi quy này.

System prompt lưu trong `backend/app/prompts/system_customer.txt`, dễ chỉnh mà không build lại.

**Considered Options**:
- Prompt cứng inline trong code — chọn cách file riêng vì dễ A/B test và không cần restart container chỉ để đổi vài câu.
- Prompt gọi qua API mỗi request — quá phức tạp cho đồ án.