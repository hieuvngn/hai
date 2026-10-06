"""Pydantic schemas cho Product, Chat, Admin, Cart, Order."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

Category = Literal["áo", "quần", "váy", "giày", "phụ kiện", "đồ thể thao"]
Gender = Literal["nam", "nữ", "unisex"]

class Product(BaseModel):
    id: str
    name: str
    brand: str
    category: Category
    description: str
    price_vnd: int = Field(ge=0)
    sizes_available: List[str]
    colors: List[str]
    material: str
    stock_per_size: Dict[str, int]
    tags: List[str]
    image_url: str
    gender: Gender
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_embedding_text(self) -> str:
        """Ghép các field văn bản thành 1 string để embed."""
        sizes = ", ".join(self.sizes_available)
        colors = ", ".join(self.colors)
        tags = ", ".join(self.tags)
        stock = ", ".join(f"{k}:{v}" for k, v in self.stock_per_size.items())
        return (
            f"Tên: {self.name}\n"
            f"Thương hiệu: {self.brand}\n"
            f"Danh mục: {self.category}\n"
            f"Mô tả: {self.description}\n"
            f"Chất liệu: {self.material}\n"
            f"Màu sắc: {colors}\n"
            f"Size có sẵn: {sizes}\n"
            f"Từ khoá: {tags}\n"
            f"Tồn kho: {stock}\n"
            f"Giới tính: {self.gender}"
        )


class ChatRequest(BaseModel):
    session_id: str
    message: str
    cart_id: Optional[str] = None
    cart_token: Optional[str] = None


class ToolCallRecord(BaseModel):
    """Một lần tool được gọi (cho lịch sử)."""
    tool: str
    arguments: dict
    result_preview: str = ""


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    products: List[Product] = Field(default_factory=list)
    """Sản phẩm được trả về trong tool results của turn này."""


# ============ Cart (canonical models owned by storage layer) ============
# Đặt giữa file có chủ đích: storage cần Product (định nghĩa ở trên) nên không thể
# đưa lên đầu file — circular import. OrderStatus cũng lấy từ storage, là nguồn
# duy nhất của nó (trước đây khai báo trùng ở cả hai file).
from .data.storage import Cart, CartItem, Order, OrderItem, OrderStatus  # noqa: E402


class CartView(BaseModel):
    """Public projection of Cart — ẩn cart_token, kèm total_vnd."""
    cart_id: str
    items: List[CartItem]
    created_at: datetime
    last_seen_at: datetime
    total_vnd: int = 0

    @classmethod
    def from_cart(cls, cart: Cart) -> "CartView":
        return cls(
            cart_id=cart.cart_id,
            items=cart.items,
            created_at=cart.created_at,
            last_seen_at=cart.last_seen_at,
            total_vnd=sum(it.price_vnd_snapshot * it.quantity for it in cart.items),
        )


class CartCreateResponse(BaseModel):
    cart_id: str
    cart_token: str


class AddToCartRequest(BaseModel):
    product_id: str
    size: str
    quantity: int = Field(ge=1)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(ge=0)


# ============ Order admin view ============

class AdminOrderRow(BaseModel):
    order_id: str
    customer_phone: str
    customer_name: str
    customer_address: str
    items: List[OrderItem]
    status: OrderStatus
    created_at: datetime
    total_vnd: int
    price_mismatch: bool = False

    @classmethod
    def from_order(cls, order: Order, price_mismatch: bool = False) -> "AdminOrderRow":
        return cls(
            order_id=order.order_id,
            customer_phone=order.customer_phone,
            customer_name=order.customer_name,
            customer_address=order.customer_address,
            items=order.items,
            status=order.status,
            created_at=order.created_at,
            total_vnd=order.total_vnd,
            price_mismatch=price_mismatch,
        )


class AdminOrdersResponse(BaseModel):
    orders: List[AdminOrderRow]
    total: int
    price_mismatch_count: int


class OrderTransitionRequest(BaseModel):
    new_status: OrderStatus


# ============ Admin ============

class AdminLoginRequest(BaseModel):
    token: str


class AdminLoginResponse(BaseModel):
    ok: bool


class AdminStats(BaseModel):
    total_products: int
    active_sessions: int
    total_customers: int
    top_products: List[Dict[str, object]]  # [{id, name, count}, ...]
    price_mismatch_count: int = 0

class AdminProductCreate(BaseModel):
    name: str
    brand: str
    category: Category
    description: str
    price_vnd: int = Field(ge=0)
    sizes_available: List[str]
    colors: List[str]
    material: str
    stock_per_size: Dict[str, int]
    tags: List[str]
    image_url: Optional[str] = None
    gender: Gender


class AdminProductUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[Category] = None
    description: Optional[str] = None
    price_vnd: Optional[int] = Field(default=None, ge=0)
    sizes_available: Optional[List[str]] = None
    colors: Optional[List[str]] = None
    material: Optional[str] = None
    stock_per_size: Optional[Dict[str, int]] = None
    tags: Optional[List[str]] = None
    image_url: Optional[str] = None
    gender: Optional[Gender] = None
