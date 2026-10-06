"""Admin routes — CRUD sản phẩm, dashboard stats, rebuild index, orders."""
from __future__ import annotations

import asyncio
import secrets
import time
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response

from ..config import get_settings
from ..log import logger
from ..rag import PRODUCTS_FILE, RagIndex
from ..data.storage import ALLOWED_TRANSITIONS, get_order_store
from ..schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminOrderRow,
    AdminOrdersResponse,
    AdminProductCreate,
    AdminProductUpdate,
    AdminStats,
    Order,
    OrderTransitionRequest,
    Product,
)
from ..session import get_store

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Phiên admin sau khi login đúng token, lưu in-memory theo sid -> expires_at.
# Hai kênh xác thực: cookie `admin_session` (trình duyệt) và Bearer <ADMIN_TOKEN>
# (curl / CI / system test). Cả hai đều so với `ADMIN_TOKEN` trong require_admin.
_SESSION_COOKIE = "admin_session"
_admin_sessions: dict[str, float] = {}  # sid -> expires_at
_SESSION_TTL = 3600


def _issue_admin_session() -> str:
    sid = secrets.token_urlsafe(24)
    _admin_sessions[sid] = time.time() + _SESSION_TTL
    return sid


def _verify_admin_session(sid: str) -> bool:
    exp = _admin_sessions.get(sid)
    if exp is None or exp < time.time():
        _admin_sessions.pop(sid, None)
        return False
    return True


def _read_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    sid = request.cookies.get(_SESSION_COOKIE)
    if sid and _verify_admin_session(sid):
        return get_settings().admin_token  # session hợp lệ, dùng token admin thật để check các request sau
    return None


def require_admin(token: str | None = Depends(_read_token)) -> str:
    expected = get_settings().admin_token
    if not token or token != expected:
        raise HTTPException(401, "Unauthorized: admin token không hợp lệ")
    return token


# ============ Login ============

@router.post("/login", response_model=AdminLoginResponse)
async def login(req: AdminLoginRequest, response: Response):
    if req.token != get_settings().admin_token:
        raise HTTPException(401, "Token không đúng")
    sid = _issue_admin_session()
    response.set_cookie(
        key=_SESSION_COOKIE,
        value=sid,
        httponly=True,
        samesite="lax",
        max_age=_SESSION_TTL,
    )
    return AdminLoginResponse(ok=True)


@router.post("/logout")
async def logout(request: Request, response: Response):
    sid = request.cookies.get(_SESSION_COOKIE)
    if sid:
        _admin_sessions.pop(sid, None)
    response.delete_cookie(_SESSION_COOKIE)
    return {"ok": True}


# ============ Helpers (lazy storage + conversion) ============

def _get_products_index_lazy():
    try:
        return RagIndex.load()
    except Exception:
        return None


def _get_products_dict_lazy():
    try:
        idx = RagIndex.load()
        return {p.id: p for p in idx.products}
    except Exception:
        return None


def _is_price_mismatch(order: Order, products_dict) -> bool:
    """Đơn 'chênh giá' khi snapshot khác giá catalog hiện tại (ADR-0008)."""
    if not products_dict:
        return False
    for it in order.items:
        prod = products_dict.get(it.product_id)
        if prod is not None and it.price_vnd_snapshot != prod.price_vnd:
            return True
    return False


def _order_to_admin_row(order: Order, products_dict=None) -> AdminOrderRow:
    return AdminOrderRow.from_order(order, price_mismatch=_is_price_mismatch(order, products_dict))

@router.get("/stats", response_model=AdminStats)
async def stats(_: str = Depends(require_admin)):
    store = get_store()
    total_products = 0
    if PRODUCTS_FILE.exists():
        with PRODUCTS_FILE.open("r", encoding="utf-8") as f:
            total_products = sum(1 for line in f if line.strip())
    active = await store.active_count()
    total_customers = await store.total_customers()
    top = await store.top_products(k=5)

    # enrich top products với tên sản phẩm — lazy-load RagIndex (same pattern as existing)
    index = _get_products_index_lazy()
    enriched: List[dict] = []
    if index:
        for entry in top:
            pid = entry["id"]
            if pid in index.by_id:
                p = index.products[index.by_id[pid]]
                enriched.append({"id": pid, "name": p.name, "count": entry["count"]})
            else:
                enriched.append(entry)
    else:
        enriched = [{"id": e["id"], "count": e["count"]} for e in top]

    # price_mismatch_count: đếm đơn pending/confirmed có snapshot ≠ giá catalog hiện tại
    price_dict = {p.id: p for p in index.products} if index is not None else _get_products_dict_lazy()
    try:
        price_mismatch_count = len(
            await get_order_store().list_all(price_mismatch_only=True, products_index=price_dict)
        )
    except Exception as e:
        logger.warning(f"price_mismatch_count compute failed: {e}")
        price_mismatch_count = 0

    return AdminStats(
        total_products=total_products,
        active_sessions=active,
        total_customers=total_customers,
        top_products=enriched,
        price_mismatch_count=price_mismatch_count,
    )

# ============ Admin Orders ============

@router.get("/orders", response_model=AdminOrdersResponse)
async def list_orders(
    _: str = Depends(require_admin),
    price_mismatch_only: bool = Query(default=False),
):
    products_dict = _get_products_dict_lazy()
    order_store = get_order_store()
    try:
        orders_raw = await order_store.list_all(
            price_mismatch_only=price_mismatch_only, products_index=products_dict
        )
    except Exception as e:
        logger.exception(f"list_orders failed: {e}")
        raise HTTPException(500, "Không lấy được orders")

    if price_mismatch_only:
        price_mismatch_count = len(orders_raw)
    else:
        try:
            price_mismatch_count = len(
                await order_store.list_all(price_mismatch_only=True, products_index=products_dict)
            )
        except Exception as e:
            logger.warning(f"price_mismatch_count failed: {e}")
            price_mismatch_count = 0

    rows = [_order_to_admin_row(o, products_dict=products_dict) for o in orders_raw]
    return AdminOrdersResponse(orders=rows, total=len(rows), price_mismatch_count=price_mismatch_count)


@router.post("/orders/{order_id}/transition", response_model=Order)
async def transition_order(
    order_id: str,
    payload: OrderTransitionRequest,
    _: str = Depends(require_admin),
):
    order_store = get_order_store()
    existing = await order_store.get(order_id)
    if existing is None:
        raise HTTPException(404, "order_id không tồn tại")

    # Chặn sớm để trả thông báo rõ ràng; OrderStore.transition cũng tự validate lại.
    allowed = ALLOWED_TRANSITIONS.get(existing.status, ())
    if payload.new_status not in allowed:
        raise HTTPException(
            422,
            f"Transition không hợp lệ: {existing.status} -> {payload.new_status}. "
            f"Allowed: {sorted(allowed)}",
        )

    try:
        updated = await order_store.transition(order_id, payload.new_status)
    except ValueError as e:
        # Storage may raise ValueError for invalid transition
        msg = str(e)
        if "transition" in msg.lower() or "allowed" in msg.lower() or "invalid" in msg.lower():
            raise HTTPException(422, msg)
        raise HTTPException(400, msg)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"transition failed: {e}")
        raise HTTPException(400, str(e))
    return updated


# ============ Products CRUD ============

def _read_products() -> List[Product]:
    out: List[Product] = []
    if not PRODUCTS_FILE.exists():
        return out
    with PRODUCTS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(Product.model_validate_json(line))
    return out


def _write_products(products: List[Product]) -> None:
    PRODUCTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PRODUCTS_FILE.open("w", encoding="utf-8") as f:
        for p in products:
            f.write(p.model_dump_json() + "\n")


def _next_id(existing: List[Product]) -> str:
    n = 1
    used = {p.id for p in existing}
    while True:
        cand = f"P{n:04d}"
        if cand not in used:
            return cand
        n += 1


@router.get("/products", response_model=List[Product])
async def list_products(_: str = Depends(require_admin)):
    return _read_products()


@router.post("/products", response_model=Product)
async def create_product(payload: AdminProductCreate, _: str = Depends(require_admin)):
    products = _read_products()
    pid = _next_id(products)
    image_url = payload.image_url or f"https://picsum.photos/seed/{pid}/400/400"
    p = Product(
        id=pid,
        name=payload.name,
        brand=payload.brand,
        category=payload.category,
        description=payload.description,
        price_vnd=payload.price_vnd,
        sizes_available=payload.sizes_available,
        colors=payload.colors,
        material=payload.material,
        stock_per_size=payload.stock_per_size,
        tags=payload.tags,
        image_url=image_url,
        gender=payload.gender,
    )
    products.append(p)
    _write_products(products)
    logger.info(f"Admin created product {pid}")
    return p


@router.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: str, payload: AdminProductUpdate, _: str = Depends(require_admin)):
    products = _read_products()
    for i, p in enumerate(products):
        if p.id == product_id:
            data = p.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            new_p = Product.model_validate(data)
            products[i] = new_p
            _write_products(products)
            logger.info(f"Admin updated product {product_id}")
            return new_p
    raise HTTPException(404, "product_id không tồn tại")


@router.delete("/products/{product_id}")
async def delete_product(product_id: str, _: str = Depends(require_admin)):
    products = _read_products()
    new = [p for p in products if p.id != product_id]
    if len(new) == len(products):
        raise HTTPException(404, "product_id không tồn tại")
    _write_products(new)
    logger.info(f"Admin deleted product {product_id}")
    return {"ok": True, "deleted": product_id}


# ============ Rebuild index ============

@router.post("/rebuild-index")
async def rebuild_index(_: str = Depends(require_admin)):
    """Chạy scripts/build_embeddings.py trong background."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "build_embeddings.py"

    async def _run():
        proc = await asyncio.create_subprocess_exec(
            "python", str(script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            logger.info(f"Rebuild index OK: {stdout.decode()[-200:]}")
        else:
            logger.error(f"Rebuild index FAIL: {stderr.decode()[-500:]}")

    asyncio.create_task(_run())
    return {"ok": True, "message": "Rebuild index đang chạy nền. Xem log server."}
