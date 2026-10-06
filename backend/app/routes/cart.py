"""Cart REST endpoints — public, X-Cart-Token header auth."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from ..log import logger
from ..schemas import AddToCartRequest, CartCreateResponse, CartView, UpdateCartItemRequest

router = APIRouter(prefix="/api/cart", tags=["cart"])


def _get_cart_store():
    from ..data.storage import get_cart_store

    return get_cart_store()


def _get_products_dict():
    """Dict[str, Product] cho CartStore.add_item kiểm tra size/tồn kho."""
    from ..rag import RagIndex

    try:
        idx = RagIndex.load()
    except Exception:
        return None
    return {p.id: p for p in idx.products}


async def _verify_cart_or_404(cart_id: str, x_cart_token: Optional[str]):
    """Cart phải tồn tại (404) và token phải khớp (401). Trả về cart."""
    if not x_cart_token:
        raise HTTPException(401, "Thiếu X-Cart-Token header")
    store = _get_cart_store()
    cart = await store.get(cart_id)
    if cart is None:
        raise HTTPException(404, "cart_id không tồn tại")
    if not await store.verify_token(cart_id, x_cart_token):
        raise HTTPException(401, "X-Cart-Token không hợp lệ")
    return cart


def _to_cart_view(cart) -> CartView:
    if cart is None:
        raise HTTPException(404, "cart_id không tồn tại")
    return CartView.from_cart(cart)


async def _touch(store, cart_id: str) -> None:
    """Gia hạn last_seen_at. Không chặn request khi ghi file lỗi."""
    try:
        await store.touch(cart_id)
    except Exception:
        logger.warning(f"cart touch failed for {cart_id}")


@router.post("", response_model=CartCreateResponse)
async def create_cart():
    store = _get_cart_store()
    cart = await store.create()
    await _touch(store, cart.cart_id)
    return CartCreateResponse(cart_id=cart.cart_id, cart_token=cart.cart_token)


@router.get("/{cart_id}", response_model=CartView)
async def get_cart(
    cart_id: str,
    x_cart_token: Optional[str] = Header(default=None, alias="X-Cart-Token"),
):
    await _verify_cart_or_404(cart_id, x_cart_token)
    store = _get_cart_store()
    await _touch(store, cart_id)
    return _to_cart_view(await store.get(cart_id))


@router.post("/{cart_id}/items", response_model=CartView)
async def add_item(
    cart_id: str,
    payload: AddToCartRequest,
    x_cart_token: Optional[str] = Header(default=None, alias="X-Cart-Token"),
):
    await _verify_cart_or_404(cart_id, x_cart_token)
    store = _get_cart_store()
    products_dict = _get_products_dict()
    if products_dict is None:
        raise HTTPException(503, "RAG index chưa sẵn sàng để kiểm tra tồn kho")
    try:
        updated = await store.add_item(
            cart_id, payload.product_id, payload.size, payload.quantity, products_dict
        )
    except ValueError as e:
        msg = str(e)
        if "product_not_found" in msg or "product_id" in msg:
            raise HTTPException(404, f"Sản phẩm không tồn tại: {payload.product_id}")
        if "size_unavailable" in msg or "size" in msg.lower():
            raise HTTPException(400, f"Size không khả dụng: {payload.size}")
        if "out_of_stock" in msg or "stock" in msg.lower():
            raise HTTPException(400, f"Hết hàng hoặc không đủ tồn kho: {msg}")
        raise HTTPException(400, msg)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"add_item failed: {e}")
        raise HTTPException(400, str(e))
    await _touch(store, cart_id)
    return _to_cart_view(updated)


@router.put("/{cart_id}/items/{product_id}/{size}", response_model=CartView)
async def update_item(
    cart_id: str,
    product_id: str,
    size: str,
    payload: UpdateCartItemRequest,
    x_cart_token: Optional[str] = Header(default=None, alias="X-Cart-Token"),
):
    await _verify_cart_or_404(cart_id, x_cart_token)
    store = _get_cart_store()
    # quantity == 0 nghĩa là xoá dòng — CartStore.update_quantity tự pop.
    try:
        updated = await store.update_quantity(cart_id, product_id, size, payload.quantity)
    except ValueError as e:
        msg = str(e)
        if "not_found" in msg or "not in cart" in msg.lower():
            raise HTTPException(404, f"Item không tồn tại trong cart: {product_id}/{size}")
        raise HTTPException(400, msg)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"update_item failed: {e}")
        raise HTTPException(400, str(e))
    await _touch(store, cart_id)
    return _to_cart_view(updated)


@router.delete("/{cart_id}/items/{product_id}/{size}", response_model=CartView)
async def delete_item(
    cart_id: str,
    product_id: str,
    size: str,
    x_cart_token: Optional[str] = Header(default=None, alias="X-Cart-Token"),
):
    await _verify_cart_or_404(cart_id, x_cart_token)
    store = _get_cart_store()
    try:
        updated = await store.remove_item(cart_id, product_id, size)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception(f"remove_item failed: {e}")
        raise HTTPException(400, str(e))
    await _touch(store, cart_id)
    return _to_cart_view(updated)
