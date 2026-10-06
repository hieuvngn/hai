"""OpenRouter client: chat completions + embeddings + retry/backoff."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from openai import AsyncOpenAI
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import get_settings
from .log import logger


class TransientError(Exception):
    """Lỗi tạm thời, có thể retry (429, 5xx, network)."""


class FatalError(Exception):
    """Lỗi không retry được (auth, bad request, model không tồn tại)."""


def _build_client() -> AsyncOpenAI:
    s = get_settings()
    if not s.openrouter_api_key:
        raise FatalError(
            "OPENROUTER_API_KEY chưa được cấu hình. Sửa .env rồi khởi động lại server."
        )
    return AsyncOpenAI(
        api_key=s.openrouter_api_key,
        base_url=s.base_url,
        default_headers={
            "HTTP-Referer": s.http_referer,
            "X-Title": s.x_title,
        },
    )


def _retry_kwargs() -> Dict[str, Any]:
    return dict(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type((TransientError, httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )


# ============ Chat ============

async def chat_completion(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: str | Dict[str, Any] = "auto",
    temperature: float = 0.7,
    max_tokens: int = 800,
) -> Dict[str, Any]:
    """Gọi /v1/chat/completions. Trả về raw response dict."""
    s = get_settings()
    client = _build_client()
    kwargs: Dict[str, Any] = dict(
        model=s.chat_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice

    async for attempt in AsyncRetrying(**_retry_kwargs()):
        with attempt:
            try:
                resp = await client.chat.completions.create(**kwargs)
                return resp.model_dump()
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                if code == 429 or 500 <= code < 600:
                    retry_after = e.response.headers.get("retry-after")
                    logger.warning(
                        f"Chat HTTP {code} (retry {attempt.retry_state.attempt_number}); retry-after={retry_after}"
                    )
                    raise TransientError(str(e)) from e
                raise FatalError(f"Chat HTTP {code}: {e.response.text}") from e
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                logger.warning(
                    f"Chat network error (retry {attempt.retry_state.attempt_number}): {e}"
                )
                raise
            except Exception as e:  # openai APIError variants
                msg = str(e)
                if "rate limit" in msg.lower() or "overloaded" in msg.lower():
                    logger.warning(f"Chat upstream 429/overload: {msg}")
                    raise TransientError(msg) from e
                raise FatalError(msg) from e


# ============ Embeddings ============

async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Gọi /v1/embeddings. Trả về list vector."""
    s = get_settings()
    client = _build_client()
    async for attempt in AsyncRetrying(**_retry_kwargs()):
        with attempt:
            try:
                resp = await client.embeddings.create(
                    model=s.embed_model,
                    input=texts,
                )
                return [d.embedding for d in resp.data]
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                if code == 429 or 500 <= code < 600:
                    raise TransientError(str(e)) from e
                if code in (400, 404):
                    # Model có thể không tồn tại cho embeddings
                    raise FatalError(
                        f"Embed model '{s.embed_model}' không khả dụng (HTTP {code}). "
                        f"Fallback sang local sentence-transformers."
                    ) from e
                raise FatalError(f"Embed HTTP {code}: {e.response.text}") from e
            except (httpx.TimeoutException, httpx.NetworkError):
                raise
            except Exception as e:
                msg = str(e)
                if "rate limit" in msg.lower() or "overloaded" in msg.lower():
                    raise TransientError(msg) from e
                raise FatalError(msg) from e


# ============ Models listing ============

async def list_supported_models() -> List[Dict[str, Any]]:
    """GET /v1/models?supported_parameters=tools — dùng cho startup log."""
    client = _build_client()
    try:
        resp = await client.models.list()
        items = resp.model_dump().get("data", [])
        # lọc theo khả năng hỗ trợ tools (nếu provider trả về supported_parameters)
        tool_models = [
            m for m in items
            if "tools" in (m.get("supported_parameters") or [])
        ]
        return tool_models or items
    except Exception as e:
        logger.warning(f"Không list được /v1/models: {e}")
        return []


async def warmup_or_die() -> None:
    """Gọi list_models lúc startup để fail-fast nếu thiếu key / model không tồn tại."""
    s = get_settings()
    if not s.openrouter_api_key:
        raise FatalError(
            "OPENROUTER_API_KEY rỗng. Đặt vào .env trước khi khởi động server."
        )
    models = await list_supported_models()
    if not models:
        logger.warning(
            "Không list được models (key hợp lệ?). Vẫn tiếp tục — sẽ lỗi khi chat."
        )
        return
    logger.info(f"Reachable models (hỗ trợ tools): {len(models)}")
    for m in models[:8]:
        logger.info(f"  - {m.get('id')} (pricing: {m.get('pricing', {})})")
    if s.chat_model not in {m.get("id") for m in models}:
        logger.warning(
            f"CHAT_MODEL '{s.chat_model}' không có trong danh sách reachable. "
            f"Vẫn tiếp tục — sẽ lỗi 404 khi chat."
        )
