"""Tool handlers — thực thi từng tool, trả dict sẽ feed lại LLM."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from ..rag import RagIndex, cosine_search
from ..rag.embedder import Embedder
from ..schemas import Product


@dataclass
class ToolResult:
    """Kết quả thực thi một tool — có cả payload gửi LLM + products để render."""
    llm_payload: Dict[str, Any]  # dict đã serialize thành JSON, sẽ wrap thành tool message
    products: List[Product]      # sản phẩm liên quan (để frontend render card)


@dataclass
class ToolContext:
    index: RagIndex
    embedder: Embedder
    cart_store: Any  # CartStore from app.data.storage
    order_store: Any  # OrderStore
    profile_store: Any  # CustomerProfileStore
    products_index: Dict[str, Product]  # alias for index.by_id -> index.products lookup
    cart_id: Optional[str]
    cart_token: Optional[str]


def _to_json_text(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _products_of_item_ids(item_ids, ctx: ToolContext) -> List[Product]:
    """Map product_id -> Product qua RAG index (bỏ id không còn trong catalog)."""
    return [
        ctx.index.products[ctx.index.by_id[pid]]
        for pid in dict.fromkeys(item_ids)
        if pid in ctx.index.by_id
    ]



# Map for complement mode per ADR-0009
COMPLEMENT_MAP: Dict[str, List[str]] = {
    "váy": ["áo", "phụ kiện", "giày"],
    "áo": ["quần", "váy", "phụ kiện"],
    "quần": ["áo", "giày", "phụ kiện"],
    "giày": ["váy", "quần", "phụ kiện"],
    "phụ kiện": ["váy", "áo", "quần"],
    "đồ thể thao": ["quần", "áo", "giày"],
}


async def handle_search_products(
    args: Dict[str, Any], ctx: ToolContext
) -> ToolResult:
    query = args["query"]
    vec = (await ctx.embedder.embed([query]))[0]
    results = cosine_search(
        ctx.index,
        query_vec=vec,
        top_k=args.get("top_k", 5),
        category=args.get("category"),
        max_price=args.get("max_price"),
        size=args.get("size"),
        color=args.get("color"),
        gender=args.get("gender"),
    )
    payload = [
        {
            "id": r.product.id,
            "name": r.product.name,
            "brand": r.product.brand,
            "category": r.product.category,
            "price_vnd": r.product.price_vnd,
            "sizes_available": r.product.sizes_available,
            "colors": r.product.colors,
            "image_url": r.product.image_url,
            "score": round(r.score, 3),
        }
        for r in results
    ]
    return ToolResult(
        llm_payload={"found": len(payload), "products": payload},
        products=[r.product for r in results],
    )


async def handle_get_product(
    args: Dict[str, Any], ctx: ToolContext
) -> ToolResult:
    pid = args["product_id"]
    if pid not in ctx.index.by_id:
        return ToolResult(
            llm_payload={"error": "product_not_found"},
            products=[],
        )
    p = ctx.index.products[ctx.index.by_id[pid]]
    return ToolResult(
        llm_payload=p.model_dump(mode="json"),
        products=[p],
    )


async def handle_check_stock(
    args: Dict[str, Any], ctx: ToolContext
) -> ToolResult:
    pid = args["product_id"]
    if pid not in ctx.index.by_id:
        return ToolResult(
            llm_payload={"error": "product_not_found"},
            products=[],
        )
    p = ctx.index.products[ctx.index.by_id[pid]]
    size = args.get("size")
    if size:
        if size not in p.sizes_available:
            return ToolResult(
                llm_payload={
                    "product_id": pid,
                    "name": p.name,
                    "size": size,
                    "in_stock": False,
                    "message": f"Size {size} không có trong danh sách size của sản phẩm này ({p.sizes_available}).",
                },
                products=[p],
            )
        qty = p.stock_per_size.get(size, 0)
        return ToolResult(
            llm_payload={
                "product_id": pid,
                "name": p.name,
                "size": size,
                "in_stock": qty > 0,
                "quantity": qty,
            },
            products=[p],
        )
    return ToolResult(
        llm_payload={
            "product_id": pid,
            "name": p.name,
            "stock_per_size": p.stock_per_size,
        },
        products=[p],
    )


async def handle_recommend_similar(
    args: Dict[str, Any], ctx: ToolContext
) -> ToolResult:
    # cart_id is required context, not user input
    if not ctx.cart_id:
        return ToolResult(
            llm_payload={"error": "cart_id_required"},
            products=[],
        )
    try:
        cart = await ctx.cart_store.get(ctx.cart_id)
    except Exception as e:
        return ToolResult(llm_payload={"error": str(e)}, products=[])
    if cart is None or not cart.items:
        return ToolResult(llm_payload={"error": "cart_is_empty"}, products=[])

    mode = args.get("mode", "similar")
    k = args.get("k", 3)
    cart_ids = {it.product_id for it in cart.items if it.product_id}

    # collect product objects for cart items
    cart_products: List[Product] = []
    for pid in cart_ids:
        if pid in ctx.index.by_id:
            cart_products.append(ctx.index.products[ctx.index.by_id[pid]])
        elif pid in ctx.products_index:
            cart_products.append(ctx.products_index[pid])

    # if no product found (invalid cart), return empty
    if not cart_products:
        return ToolResult(llm_payload={"error": "cart_is_empty"}, products=[])

    scored: Dict[str, Any] = {}  # id -> ScoredProduct (keep best score)
    # For each cart item, do search
    for base_product in cart_products:
        base_id = base_product.id
        base_idx = ctx.index.by_id.get(base_id)
        if base_idx is None:
            continue
        base_vec = ctx.index.embeddings[base_idx]
        # compute sims to all
        # avoid division by zero
        norm_base = float(np.linalg.norm(base_vec))
        if norm_base == 0:
            norm_base = 1e-9
        # embeddings @ base_vec / (norms * norm_base)
        emb_norms = np.linalg.norm(ctx.index.embeddings, axis=1)
        emb_norms = np.where(emb_norms == 0, 1e-9, emb_norms)
        sims = ctx.index.embeddings @ base_vec / (emb_norms * norm_base + 1e-9)

        if mode == "similar":
            # same category, exclude self and cart items
            candidates = []
            for idx, p in enumerate(ctx.index.products):
                if p.id == base_id:
                    continue
                if p.id in cart_ids and p.id != base_id:
                    # exclude other cart items as well? spec says dedupe, but not explicitly exclude cart items; we exclude to avoid recommending already in cart
                    # keep exclusion to improve UX
                    continue
                if p.category != base_product.category:
                    continue
                candidates.append((p, float(sims[idx])))
            candidates.sort(key=lambda x: x[1], reverse=True)
            for p, score in candidates[:k]:
                # dedupe: keep highest score
                if p.id not in scored or scored[p.id].score < score:
                    from ..rag.retriever import ScoredProduct
                    scored[p.id] = ScoredProduct(product=p, score=score)
        else:  # complement
            allowed = COMPLEMENT_MAP.get(base_product.category, [])
            if not allowed:
                continue
            allowed_set = set(allowed)
            candidates = []
            for idx, p in enumerate(ctx.index.products):
                if p.id == base_id:
                    continue
                if p.id in cart_ids:
                    continue
                if p.category not in allowed_set:
                    continue
                candidates.append((p, float(sims[idx])))
            candidates.sort(key=lambda x: x[1], reverse=True)
            for p, score in candidates[:k]:
                if p.id not in scored or scored[p.id].score < score:
                    from ..rag.retriever import ScoredProduct
                    scored[p.id] = ScoredProduct(product=p, score=score)

    # merge and sort globally
    all_scored = list(scored.values())
    all_scored.sort(key=lambda c: c.score, reverse=True)
    top = all_scored[:k]

    payload = [
        {
            "id": r.product.id,
            "name": r.product.name,
            "brand": r.product.brand,
            "category": r.product.category,
            "price_vnd": r.product.price_vnd,
            "sizes_available": r.product.sizes_available,
            "image_url": r.product.image_url,
            "score": round(r.score, 3),
        }
        for r in top
    ]
    return ToolResult(
        llm_payload={"mode": mode, "similar": payload} if mode == "similar" else {"mode": mode, "complement": payload},
        products=[r.product for r in top],
    )


async def handle_add_to_cart(
    args: Dict[str, Any], ctx: ToolContext
) -> ToolResult:
    if not ctx.cart_id:
        return ToolResult(llm_payload={"error": "cart_id_required"}, products=[])
    product_id = args.get("product_id")
    size = args.get("size")
    quantity = args.get("quantity", 1)
    if not product_id or not size:
        return ToolResult(llm_payload={"error": "product_id and size required"}, products=[])
    # quick product existence check
    if product_id not in ctx.index.by_id and (not ctx.products_index or product_id not in ctx.products_index):
        return ToolResult(llm_payload={"error": "product_not_found"}, products=[])
    try:
        cart = await ctx.cart_store.add_item(
            ctx.cart_id, product_id, size, quantity, ctx.products_index
        )
        products = _products_of_item_ids((it.product_id for it in cart.items), ctx)
        return ToolResult(llm_payload=cart.model_dump(mode="json"), products=products)
    except ValueError as e:
        return ToolResult(llm_payload={"error": str(e)}, products=[])
    except Exception as e:
        return ToolResult(llm_payload={"error": str(e)}, products=[])


async def handle_get_cart(
    args: Dict[str, Any], ctx: ToolContext
) -> ToolResult:
    if not ctx.cart_id:
        return ToolResult(llm_payload={"error": "cart_id_required"}, products=[])
    try:
        cart = await ctx.cart_store.get(ctx.cart_id)
        if cart is None:
            return ToolResult(llm_payload={"error": "cart_not_found"}, products=[])
        products = _products_of_item_ids((it.product_id for it in cart.items), ctx)
        return ToolResult(llm_payload=cart.model_dump(mode="json"), products=products)
    except ValueError as e:
        return ToolResult(llm_payload={"error": str(e)}, products=[])
    except Exception as e:
        return ToolResult(llm_payload={"error": str(e)}, products=[])


async def handle_update_customer_profile(
    args: Dict[str, Any], ctx: ToolContext
) -> ToolResult:
    phone = args.get("phone")
    name = args.get("name")
    address = args.get("address")
    if not phone or not name or not address:
        return ToolResult(llm_payload={"error": "phone, name, address required"}, products=[])
    try:
        profile = await ctx.profile_store.upsert(phone, name, address)
        return ToolResult(llm_payload=profile.model_dump(mode="json"), products=[])
    except ValueError as e:
        return ToolResult(llm_payload={"error": str(e)}, products=[])
    except Exception as e:
        return ToolResult(llm_payload={"error": str(e)}, products=[])


async def handle_create_order(
    args: Dict[str, Any], ctx: ToolContext
) -> ToolResult:
    if not ctx.cart_id:
        return ToolResult(llm_payload={"error": "cart_id_required"}, products=[])
    phone = args.get("phone")
    if not phone:
        return ToolResult(llm_payload={"error": "phone_required"}, products=[])
    try:
        profile = await ctx.profile_store.get(phone)
        if profile is None:
            return ToolResult(llm_payload={"error": "profile_not_found"}, products=[])
        cart = await ctx.cart_store.get(ctx.cart_id)
        if cart is None:
            return ToolResult(llm_payload={"error": "cart_not_found"}, products=[])
        if not cart.items:
            return ToolResult(llm_payload={"error": "cart_is_empty"}, products=[])
        order = await ctx.order_store.create_from_cart(cart, profile)
        products = _products_of_item_ids((it.product_id for it in order.items), ctx)
        return ToolResult(llm_payload=order.model_dump(mode="json"), products=products)
    except ValueError as e:
        return ToolResult(llm_payload={"error": str(e)}, products=[])
    except Exception as e:
        return ToolResult(llm_payload={"error": str(e)}, products=[])


DISPATCH = {
    "search_products": handle_search_products,
    "get_product": handle_get_product,
    "check_stock": handle_check_stock,
    "recommend_similar": handle_recommend_similar,
    "add_to_cart": handle_add_to_cart,
    "get_cart": handle_get_cart,
    "update_customer_profile": handle_update_customer_profile,
    "create_order": handle_create_order,
}


def list_tool_names() -> List[str]:
    return list(DISPATCH.keys())
