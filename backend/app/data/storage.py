"""Persistent storage layer for Cart, Order, CustomerProfile.

Pattern: in-memory dict + JSONL file on disk, whole-file rewrite, asyncio.Lock.
Matches products persistence in `app/routes/admin.py` (in-memory dict + JSONL).
"""

from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Set

from pydantic import BaseModel, Field

from ..log import logger
if TYPE_CHECKING:
    # Chỉ dùng trong annotation của các method thường (không phải Pydantic model) và
    # `from __future__ import annotations` không ép buộc resolve — nên import ở runtime
    # là vô ích và tạo vòng lặp schemas ↔ storage khiến `import app.data.storage`
    # làm module đầu tiên sẽ nổ ImportError.
    from ..schemas import Product

# ---------------------------------------------------------------------------
# File locations (backend/data/*.jsonl)
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CARTS_FILE = DATA_DIR / "carts.jsonl"
ORDERS_FILE = DATA_DIR / "orders.jsonl"
CUSTOMER_PROFILES_FILE = DATA_DIR / "customer_profiles.jsonl"

# ---------------------------------------------------------------------------
# Order status transition table
# ---------------------------------------------------------------------------
OrderStatus = Literal["pending", "confirmed", "shipped", "completed", "cancelled", "failed"]

ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"shipped", "cancelled"},
    "shipped": {"completed", "failed"},
    "completed": set(),
    "cancelled": set(),
    "failed": set(),
}

# ---------------------------------------------------------------------------
# Pydantic models — storage owns them, schemas.py may re-export for API.
# ---------------------------------------------------------------------------


class CartItem(BaseModel):
    product_id: str
    size: str
    quantity: int = Field(ge=1)
    price_vnd_snapshot: int
    name_snapshot: str
    image_url_snapshot: str


class Cart(BaseModel):
    cart_id: str
    cart_token: str  # 256-bit secret used as bearer credential
    created_at: datetime
    last_seen_at: datetime
    items: List[CartItem]


class OrderItem(BaseModel):
    product_id: str
    size: str
    quantity: int
    price_vnd_snapshot: int
    name_snapshot: str
    image_url_snapshot: str


class Order(BaseModel):
    order_id: str
    customer_phone: str
    customer_name: str
    customer_address: str
    items: List[OrderItem]
    status: OrderStatus  # type: ignore[valid-type]
    created_at: datetime
    status_history: List[Dict[str, str]]  # [{status, at}, ...]
    total_vnd: int  # computed at create: sum(price_vnd_snapshot * quantity)


class CustomerProfile(BaseModel):
    phone: str  # identity (strip whitespace, keep as-is)
    name: str
    address: str
    created_at: datetime
    last_seen_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# CartStore
# ---------------------------------------------------------------------------


class CartStore:
    def __init__(self) -> None:
        self._carts: Dict[str, Cart] = {}
        self._lock = asyncio.Lock()
        self._load()

    # -- persistence helpers (sync, called with lock held) -----------------

    def _load(self) -> None:
        if not CARTS_FILE.exists():
            return
        try:
            with CARTS_FILE.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        cart = Cart.model_validate_json(line)
                    except Exception:
                        logger.warning(f"Skipping invalid cart line: {line[:120]}")
                        continue
                    self._carts[cart.cart_id] = cart
        except Exception as e:
            logger.warning(f"CartStore load failed: {e}")

    def _save(self) -> None:
        CARTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CARTS_FILE.open("w", encoding="utf-8") as f:
            for cart in self._carts.values():
                f.write(cart.model_dump_json() + "\n")

    # -- public async API --------------------------------------------------

    async def create(self) -> Cart:
        async with self._lock:
            # generate unique cart_id
            while True:
                cart_id = secrets.token_urlsafe(16)
                if cart_id not in self._carts:
                    break
            cart_token = secrets.token_urlsafe(32)
            now = _now()
            cart = Cart(
                cart_id=cart_id,
                cart_token=cart_token,
                created_at=now,
                last_seen_at=now,
                items=[],
            )
            self._carts[cart_id] = cart
            self._save()
            logger.info(f"Cart created {cart_id}")
            return cart

    async def get(self, cart_id: str) -> Optional[Cart]:
        async with self._lock:
            return self._carts.get(cart_id)

    async def touch(self, cart_id: str) -> None:
        async with self._lock:
            cart = self._carts.get(cart_id)
            if cart is None:
                return
            cart.last_seen_at = _now()
            # Cart is a Pydantic model; mutation via attribute works, but to be safe
            # we replace entry (Pydantic allows attribute assignment)
            self._carts[cart_id] = cart
            self._save()

    async def verify_token(self, cart_id: str, token: str) -> bool:
        async with self._lock:
            cart = self._carts.get(cart_id)
            if cart is None:
                return False
            # constant-time compare
            try:
                return secrets.compare_digest(cart.cart_token, token)
            except Exception:
                return cart.cart_token == token

    async def add_item(
        self,
        cart_id: str,
        product_id: str,
        size: str,
        quantity: int,
        products_index: Dict[str, Product],
    ) -> Cart:
        async with self._lock:
            cart = self._carts.get(cart_id)
            if cart is None:
                raise ValueError("cart_not_found")

            if quantity < 1:
                raise ValueError("invalid_quantity")

            product = products_index.get(product_id)
            if product is None:
                raise ValueError("product_not_found")

            if size not in product.sizes_available:
                raise ValueError("size_unavailable")

            available = product.stock_per_size.get(size, 0)

            # find existing item
            existing_idx: Optional[int] = None
            existing_qty = 0
            for idx, it in enumerate(cart.items):
                if it.product_id == product_id and it.size == size:
                    existing_idx = idx
                    existing_qty = it.quantity
                    break

            merged_quantity = existing_qty + quantity
            if merged_quantity > available:
                raise ValueError("out_of_stock", product_id, size, merged_quantity, available)

            now = _now()
            if existing_idx is not None:
                # merge: sum quantity, refresh snapshot to current product values
                cart.items[existing_idx] = CartItem(
                    product_id=product_id,
                    size=size,
                    quantity=merged_quantity,
                    price_vnd_snapshot=product.price_vnd,
                    name_snapshot=product.name,
                    image_url_snapshot=product.image_url,
                )
            else:
                cart.items.append(
                    CartItem(
                        product_id=product_id,
                        size=size,
                        quantity=quantity,
                        price_vnd_snapshot=product.price_vnd,
                        name_snapshot=product.name,
                        image_url_snapshot=product.image_url,
                    )
                )
            cart.last_seen_at = now
            self._carts[cart_id] = cart
            self._save()
            return cart

    async def update_quantity(
        self,
        cart_id: str,
        product_id: str,
        size: str,
        quantity: int,
    ) -> Cart:
        async with self._lock:
            cart = self._carts.get(cart_id)
            if cart is None:
                raise ValueError("cart_not_found")
            if quantity < 0:
                raise ValueError("invalid_quantity")
            idx: Optional[int] = None
            for i, it in enumerate(cart.items):
                if it.product_id == product_id and it.size == size:
                    idx = i
                    break
            if idx is None:
                raise ValueError("item_not_found")
            if quantity == 0:
                cart.items.pop(idx)
            else:
                # keep snapshot as-is, only change quantity
                old = cart.items[idx]
                cart.items[idx] = CartItem(
                    product_id=old.product_id,
                    size=old.size,
                    quantity=quantity,
                    price_vnd_snapshot=old.price_vnd_snapshot,
                    name_snapshot=old.name_snapshot,
                    image_url_snapshot=old.image_url_snapshot,
                )
            cart.last_seen_at = _now()
            self._carts[cart_id] = cart
            self._save()
            return cart

    async def remove_item(self, cart_id: str, product_id: str, size: str) -> Cart:
        async with self._lock:
            cart = self._carts.get(cart_id)
            if cart is None:
                raise ValueError("cart_not_found")
            original_len = len(cart.items)
            cart.items = [it for it in cart.items if not (it.product_id == product_id and it.size == size)]
            if len(cart.items) == original_len:
                raise ValueError("item_not_found")
            cart.last_seen_at = _now()
            self._carts[cart_id] = cart
            self._save()
            return cart

    async def clear(self, cart_id: str) -> None:
        async with self._lock:
            cart = self._carts.get(cart_id)
            if cart is None:
                raise ValueError("cart_not_found")
            cart.items = []
            cart.last_seen_at = _now()
            self._carts[cart_id] = cart
            self._save()

    async def sweep_expired(self, ttl_seconds: int) -> int:
        async with self._lock:
            now = _now()
            expired: List[str] = []
            for cid, cart in self._carts.items():
                # ensure timezone-aware comparison
                last = cart.last_seen_at
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                age = (now - last).total_seconds()
                if age > ttl_seconds:
                    expired.append(cid)
            for cid in expired:
                self._carts.pop(cid, None)
            if expired:
                self._save()
                logger.info(f"CartStore swept {len(expired)} expired carts")
            return len(expired)


# ---------------------------------------------------------------------------
# OrderStore
# ---------------------------------------------------------------------------


class OrderStore:
    def __init__(self) -> None:
        self._orders: Dict[str, Order] = {}
        self._lock = asyncio.Lock()
        self._load()

    def _load(self) -> None:
        if not ORDERS_FILE.exists():
            return
        try:
            with ORDERS_FILE.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        order = Order.model_validate_json(line)
                    except Exception:
                        logger.warning(f"Skipping invalid order line: {line[:120]}")
                        continue
                    self._orders[order.order_id] = order
        except Exception as e:
            logger.warning(f"OrderStore load failed: {e}")

    def _save(self) -> None:
        ORDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ORDERS_FILE.open("w", encoding="utf-8") as f:
            for order in self._orders.values():
                f.write(order.model_dump_json() + "\n")

    async def create_from_cart(self, cart: Cart, profile: CustomerProfile) -> Order:
        async with self._lock:
            if not cart.items:
                raise ValueError("empty_cart")
            # generate unique order_id
            while True:
                order_id = f"ORD-{secrets.token_urlsafe(8)}"
                if order_id not in self._orders:
                    break
            now = _now()
            order_items: List[OrderItem] = []
            for ci in cart.items:
                order_items.append(
                    OrderItem(
                        product_id=ci.product_id,
                        size=ci.size,
                        quantity=ci.quantity,
                        price_vnd_snapshot=ci.price_vnd_snapshot,
                        name_snapshot=ci.name_snapshot,
                        image_url_snapshot=ci.image_url_snapshot,
                    )
                )
            total_vnd = sum(oi.price_vnd_snapshot * oi.quantity for oi in order_items)
            order = Order(
                order_id=order_id,
                customer_phone=profile.phone,
                customer_name=profile.name,
                customer_address=profile.address,
                items=order_items,
                status="pending",
                created_at=now,
                status_history=[{"status": "pending", "at": now.isoformat()}],
                total_vnd=total_vnd,
            )
            self._orders[order_id] = order
            self._save()
            logger.info(f"Order {order_id} created from cart {cart.cart_id} total={total_vnd}")
            return order

    async def get(self, order_id: str) -> Optional[Order]:
        async with self._lock:
            return self._orders.get(order_id)

    async def list_all(
        self,
        price_mismatch_only: bool = False,
        products_index: Optional[Dict[str, Product]] = None,
    ) -> List[Order]:
        async with self._lock:
            orders = list(self._orders.values())
            if not price_mismatch_only:
                return orders
            if products_index is None:
                return []
            out: List[Order] = []
            for order in orders:
                if order.status not in ("pending", "confirmed"):
                    continue
                mismatch = False
                for item in order.items:
                    prod = products_index.get(item.product_id)
                    if prod is None:
                        continue
                    if item.price_vnd_snapshot != prod.price_vnd:
                        mismatch = True
                        break
                if mismatch:
                    out.append(order)
            return out

    async def transition(self, order_id: str, new_status: OrderStatus) -> Order:  # type: ignore[valid-type]
        async with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                raise ValueError("order_not_found")
            allowed = ALLOWED_TRANSITIONS.get(order.status, set())
            if new_status not in allowed:
                raise ValueError("invalid_transition", order.status, new_status)
            now = _now()
            order.status = new_status  # type: ignore[assignment]
            order.status_history.append({"status": new_status, "at": now.isoformat()})
            self._orders[order_id] = order
            self._save()
            logger.info(f"Order {order_id} transition {order.status} -> {new_status}")
            return order

    async def list_by_phone(self, phone: str) -> List[Order]:
        async with self._lock:
            norm = phone.strip()
            return [o for o in self._orders.values() if o.customer_phone.strip() == norm]


# ---------------------------------------------------------------------------
# CustomerProfileStore
# ---------------------------------------------------------------------------


class CustomerProfileStore:
    def __init__(self) -> None:
        self._profiles: Dict[str, CustomerProfile] = {}
        self._lock = asyncio.Lock()
        self._load()

    def _load(self) -> None:
        if not CUSTOMER_PROFILES_FILE.exists():
            return
        try:
            with CUSTOMER_PROFILES_FILE.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        prof = CustomerProfile.model_validate_json(line)
                    except Exception:
                        logger.warning(f"Skipping invalid profile line: {line[:120]}")
                        continue
                    # normalize key on load as well (strip)
                    key = prof.phone.strip()
                    self._profiles[key] = prof
        except Exception as e:
            logger.warning(f"CustomerProfileStore load failed: {e}")

    def _save(self) -> None:
        CUSTOMER_PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CUSTOMER_PROFILES_FILE.open("w", encoding="utf-8") as f:
            for prof in self._profiles.values():
                f.write(prof.model_dump_json() + "\n")

    async def upsert(self, phone: str, name: str, address: str) -> CustomerProfile:
        async with self._lock:
            norm = phone.strip()
            now = _now()
            existing = self._profiles.get(norm)
            if existing is not None:
                updated = CustomerProfile(
                    phone=norm,
                    name=name,
                    address=address,
                    created_at=existing.created_at,
                    last_seen_at=now,
                )
                self._profiles[norm] = updated
                self._save()
                return updated
            else:
                prof = CustomerProfile(
                    phone=norm,
                    name=name,
                    address=address,
                    created_at=now,
                    last_seen_at=now,
                )
                self._profiles[norm] = prof
                self._save()
                logger.info(f"Profile created {norm}")
                return prof

    async def get(self, phone: str) -> Optional[CustomerProfile]:
        async with self._lock:
            norm = phone.strip()
            return self._profiles.get(norm)

    async def touch(self, phone: str) -> None:
        async with self._lock:
            norm = phone.strip()
            prof = self._profiles.get(norm)
            if prof is None:
                return
            updated = CustomerProfile(
                phone=prof.phone,
                name=prof.name,
                address=prof.address,
                created_at=prof.created_at,
                last_seen_at=_now(),
            )
            self._profiles[norm] = updated
            self._save()

    async def sweep_expired(self, ttl_seconds: int) -> int:
        async with self._lock:
            now = _now()
            expired: List[str] = []
            for phone, prof in self._profiles.items():
                last = prof.last_seen_at
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                age = (now - last).total_seconds()
                if age > ttl_seconds:
                    expired.append(phone)
            for phone in expired:
                self._profiles.pop(phone, None)
            if expired:
                self._save()
                logger.info(f"ProfileStore swept {len(expired)} expired profiles")
            return len(expired)


# ---------------------------------------------------------------------------
# Module-level singletons (same pattern as app/session.py:get_store())
# ---------------------------------------------------------------------------

_cart_store: Optional[CartStore] = None
_order_store: Optional[OrderStore] = None
_profile_store: Optional[CustomerProfileStore] = None


def get_cart_store() -> CartStore:
    global _cart_store
    if _cart_store is None:
        _cart_store = CartStore()
    return _cart_store


def get_order_store() -> OrderStore:
    global _order_store
    if _order_store is None:
        _order_store = OrderStore()
    return _order_store


def get_profile_store() -> CustomerProfileStore:
    global _profile_store
    if _profile_store is None:
        _profile_store = CustomerProfileStore()
    return _profile_store


# ---------------------------------------------------------------------------
# Background sweeper for cart/profile TTL (carts 7 days, profiles 90 days)
# Called from main.py lifespan.
# ---------------------------------------------------------------------------


async def storage_sweeper_loop(interval_seconds: int = 3600) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await get_cart_store().sweep_expired(7 * 86400)
            await get_profile_store().sweep_expired(90 * 86400)
        except Exception as e:
            logger.exception(f"storage_sweeper_loop error: {e}")


__all__ = [
    "CartItem",
    "Cart",
    "OrderItem",
    "Order",
    "OrderStatus",
    "CustomerProfile",
    "ALLOWED_TRANSITIONS",
    "CartStore",
    "OrderStore",
    "CustomerProfileStore",
    "get_cart_store",
    "get_order_store",
    "get_profile_store",
    "storage_sweeper_loop",
    "CARTS_FILE",
    "ORDERS_FILE",
    "CUSTOMER_PROFILES_FILE",
]
