"""JSON Schema cho tool khách."""
from __future__ import annotations

CUSTOMER_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Tìm sản phẩm thời trang trong catalog. Dùng khi khách mô tả nhu cầu "
                "(danh mục, phong cách, dịp, ngân sách). Có thể kèm filter cứng."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Mô tả nhu cầu bằng tiếng Việt, vd 'váy công sở mùa hè dưới 1 triệu'.",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["áo", "quần", "váy", "giày", "phụ kiện", "đồ thể thao"],
                        "description": "Lọc theo danh mục.",
                    },
                    "size": {
                        "type": "string",
                        "description": "Lọc theo size có sẵn, vd 'M', 'XL'.",
                    },
                    "max_price": {
                        "type": "integer",
                        "description": "Giá tối đa (VND).",
                    },
                    "color": {
                        "type": "string",
                        "description": "Lọc theo màu sắc, vd 'đen', 'trắng'.",
                    },
                    "gender": {
                        "type": "string",
                        "enum": ["nam", "nữ", "unisex"],
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": "Lấy chi tiết đầy đủ của một sản phẩm theo ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "Kiểm tra tồn kho của một sản phẩm theo size (hoặc tất cả size).",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "size": {
                        "type": "string",
                        "description": "Size cụ thể. Bỏ trống để xem tất cả.",
                    },
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_similar",
            "description": "Gợi ý sản phẩm dựa trên giỏ hàng hiện tại của khách. mode='similar' tìm sản phẩm cùng danh mục, embedding gần. mode='complement' tìm sản phẩm danh mục khác hay đi kèm (váy→áo/phụ kiện/giày, áo→quần/váy/phụ kiện, ...).",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["similar", "complement"], "default": "similar"},
                    "k": {"type": "integer", "default": 3, "minimum": 1, "maximum": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": "Thêm sản phẩm vào giỏ hàng. Yêu cầu khách đã có cart_id (chat sẽ tự cung cấp). Trước khi gọi tool này, đã gọi check_stock để xác nhận còn hàng.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "size": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1, "default": 1},
                },
                "required": ["product_id", "size"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cart",
            "description": "Lấy nội dung giỏ hàng hiện tại của khách.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_customer_profile",
            "description": "Lưu hoặc cập nhật thông tin khách (tên, số điện thoại, địa chỉ giao hàng) để tạo đơn. Hỏi khách các thông tin này trước khi gọi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Số điện thoại Việt Nam."},
                    "name": {"type": "string"},
                    "address": {"type": "string"},
                },
                "required": ["phone", "name", "address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Tạo đơn hàng từ giỏ hiện tại. Yêu cầu khách đã cung cấp phone/name/address (đã gọi update_customer_profile trước đó). Sau khi tạo, đơn ở trạng thái 'pending' và chờ admin duyệt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                },
                "required": ["phone"],
            },
        },
    },
]
