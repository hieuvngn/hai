"""Public routes — health, model listing, product browse, single product lookup."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from ..llm import list_supported_models
from ..rag import PRODUCTS_FILE
from ..schemas import Product

router = APIRouter(prefix="/api", tags=["public"])

VALID_CATEGORIES = ["áo", "quần", "váy", "giày", "phụ kiện", "đồ thể thao"]


def _load_products_fallback() -> list[Product]:
    """Read products.jsonl directly — 5-line simple read like admin._read_products."""
    out: list[Product] = []
    if not PRODUCTS_FILE.exists():
        return out
    with PRODUCTS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(Product.model_validate_json(line))
    return out


def _get_products(request: Request) -> list[Product]:
    idx = getattr(request.app.state, "rag_index", None)
    if idx is not None and hasattr(idx, "products"):
        return idx.products
    return _load_products_fallback()


@router.get("/health")
async def health():
    return {"ok": True}


@router.get("/models")
async def models():
    items = await list_supported_models()
    return {"count": len(items), "models": [{"id": m.get("id"), "pricing": m.get("pricing", {})} for m in items]}


@router.get("/products")
async def list_products(
    request: Request,
    category: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    min_price: Optional[int] = Query(default=None, ge=0),
    max_price: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    if category is not None and category not in VALID_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"category phải là một trong {VALID_CATEGORIES}")
    if min_price is not None and max_price is not None and max_price < min_price:
        raise HTTPException(status_code=422, detail="max_price phải >= min_price")

    products = _get_products(request)
    # Sort by id ascending for stable pagination
    products = sorted(products, key=lambda p: p.id)

    # Filter by category
    if category is not None:
        products = [p for p in products if p.category == category]

    # Filter by search (case-insensitive substring on name, description, brand)
    if search is not None and search.strip() != "":
        q = search.strip().lower()
        products = [
            p
            for p in products
            if q in p.name.lower() or q in p.description.lower() or q in p.brand.lower()
        ]

    # Filter by price
    if min_price is not None:
        products = [p for p in products if p.price_vnd >= min_price]
    if max_price is not None:
        products = [p for p in products if p.price_vnd <= max_price]

    total = len(products)
    items = products[offset : offset + limit]
    return {"total": total, "items": items}


@router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str, request: Request):
    index = getattr(request.app.state, "rag_index", None)
    if index is None:
        raise HTTPException(503, "RAG index chưa sẵn sàng")
    if product_id not in index.by_id:
        raise HTTPException(404, "product_id không tồn tại")
    return index.products[index.by_id[product_id]]
