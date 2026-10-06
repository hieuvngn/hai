"""Order customer lookup — public GET /api/orders/me?phone=."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Query

from ..log import logger
from ..schemas import Order

router = APIRouter(prefix="/api", tags=["orders"])


def _get_order_store():
    from ..data.storage import get_order_store

    return get_order_store()


@router.get("/orders/me", response_model=List[Order])
async def list_my_orders(phone: str = Query(..., description="Số điện thoại khách hàng")):
    phone = phone.strip()
    if not phone:
        raise HTTPException(400, "phone không được để trống")
    store = _get_order_store()
    try:
        # OrderStore trả về List[Order] — schemas.Order CHÍNH LÀ model đó (re-export
        # từ storage), nên không cần bước chuyển đổi.
        orders: List[Order] = await store.list_by_phone(phone)
    except Exception as e:
        logger.exception(f"list_by_phone failed: {e}")
        raise HTTPException(500, "Không lấy được orders")
    return orders
