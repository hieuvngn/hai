"""Chat route — khách gửi message, server loop tool-calling tới khi có final text."""
from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, HTTPException, Request

from ..data.storage import get_cart_store, get_order_store, get_profile_store
from ..llm import FatalError, chat_completion
from ..log import logger
from ..prompts import load_customer_prompt
from ..schemas import (
    ChatRequest,
    ChatResponse,
    Product,
    ToolCallRecord,
)
from ..session import get_store
from ..tools import CUSTOMER_TOOLS, DISPATCH
from ..tools.handlers import ToolContext, ToolResult

router = APIRouter(prefix="/api", tags=["chat"])




@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    index = request.app.state.rag_index
    if index is None:
        raise HTTPException(503, "RAG index chưa sẵn sàng. Chạy scripts/generate_dataset.py + scripts/build_embeddings.py.")

    store = get_store()
    session = await store.get_or_create(req.session_id, is_admin=False)

    # append user message
    session.messages.append({"role": "user", "content": req.message})

    messages_for_llm = [{"role": "system", "content": load_customer_prompt()}]
    messages_for_llm.extend(session.messages)

    tool_calls_recorded: List[ToolCallRecord] = []
    products_this_turn: List[Product] = []

    ctx = ToolContext(
        index=index,
        embedder=request.app.state.embedder,
        cart_store=get_cart_store(),
        order_store=get_order_store(),
        profile_store=get_profile_store(),
        products_index={p.id: p for p in index.products},
        cart_id=req.cart_id,
        cart_token=req.cart_token,
    )

    # Loop tool-calling tối đa 5 vòng để tránh infinite loop
    for _ in range(5):
        try:
            resp = await chat_completion(
                messages=messages_for_llm,
                tools=CUSTOMER_TOOLS,
                tool_choice="auto",
            )
        except FatalError as e:
            logger.error(f"Chat fatal: {e}")
            raise HTTPException(502, f"OpenRouter lỗi: {e}")

        msg = resp["choices"][0]["message"]
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            # final answer
            session.messages.append({
                "role": "assistant",
                "content": msg.get("content") or "",
            })
            return ChatResponse(
                session_id=req.session_id,
                reply=msg.get("content") or "",
                tool_calls=tool_calls_recorded,
                products=products_this_turn,
            )

        # append assistant message (with tool_calls) vào history
        session.messages.append(msg)
        messages_for_llm.append(msg)

        # thực thi từng tool
        for tc in tool_calls:
            tname = tc["function"]["name"]
            try:
                targs = json.loads(tc["function"]["arguments"])
            except Exception:
                targs = {}
            handler = DISPATCH.get(tname)
            call_products: List[Product] = []
            if handler is None:
                result = {"error": f"tool '{tname}' không tồn tại"}
            else:
                try:
                    tr = await handler(targs, ctx)
                except Exception as e:
                    # Handler nhận args từ LLM — thiếu/sai field không được làm sập cả turn.
                    logger.exception(f"tool {tname} failed: {e}")
                    tr = ToolResult(llm_payload={"error": f"tool '{tname}' lỗi: {e}"}, products=[])
                result = tr.llm_payload
                call_products = tr.products

            # Chỉ đưa sản phẩm của chính tool-call này vào bộ đếm: `products_this_turn`
            # là danh sách gom cho response nên đã chứa sản phẩm của các tool-call trước
            # cùng lượt — truyền nó vào track_tool_call sẽ đếm trùng mỗi sản phẩm lặp lại.
            products_this_turn.extend(call_products)
            tool_calls_recorded.append(
                ToolCallRecord(tool=tname, arguments=targs, result_preview=str(result)[:200])
            )
            await store.track_tool_call(req.session_id, tname, targs, call_products)

            tool_message = {
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            }
            session.messages.append(tool_message)
            messages_for_llm.append(tool_message)

    raise HTTPException(500, "Quá nhiều tool-call turns (>5). Vui lòng thử lại.")
