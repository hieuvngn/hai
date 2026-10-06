"""In-memory session store + TTL sweeper."""
from __future__ import annotations

import asyncio
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import get_settings
from .log import logger
from .schemas import Product


@dataclass
class SessionRecord:
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    messages: List[dict] = field(default_factory=list)  # OpenAI chat messages
    tool_calls: List[dict] = field(default_factory=list)
    products_consulted: Counter = field(default_factory=Counter)
    """Đếm số turn mà sản phẩm nào xuất hiện trong tool result (cho dashboard top products)."""
    is_admin: bool = False
    """Đánh dấu đây là phiên admin (qua /api/admin/login)."""


class SessionStore:
    def __init__(self) -> None:
        self._store: Dict[str, SessionRecord] = {}
        self._total_customers_seen: int = 0
        self._lock = asyncio.Lock()

    async def get_or_create(self, session_id: str, is_admin: bool = False) -> SessionRecord:
        async with self._lock:
            rec = self._store.get(session_id)
            if rec is None:
                rec = SessionRecord(session_id=session_id, is_admin=is_admin)
                self._store[session_id] = rec
                if not is_admin:
                    self._total_customers_seen += 1
            rec.last_seen = time.time()
            if rec.is_admin != is_admin:
                rec.is_admin = is_admin
            return rec

    async def append_message(self, session_id: str, message: dict) -> None:
        rec = await self.get_or_create(session_id)
        rec.messages.append(message)
        rec.last_seen = time.time()

    async def track_tool_call(self, session_id: str, tool: str, args: dict, products: List[Product]) -> None:
        rec = await self.get_or_create(session_id)
        rec.tool_calls.append({"tool": tool, "arguments": args})
        for p in products:
            rec.products_consulted[p.id] += 1

    async def touch(self, session_id: str) -> None:
        rec = await self.get_or_create(session_id)
        rec.last_seen = time.time()

    async def active_count(self) -> int:
        ttl = get_settings().session_ttl_seconds
        cutoff = time.time() - ttl
        return sum(1 for r in self._store.values() if r.last_seen >= cutoff and not r.is_admin)

    async def total_customers(self) -> int:
        return self._total_customers_seen

    async def top_products(self, k: int = 5) -> List[Dict[str, object]]:
        ttl = get_settings().session_ttl_seconds
        cutoff = time.time() - ttl
        agg: Counter[str] = Counter()
        for rec in self._store.values():
            if rec.last_seen < cutoff:
                continue
            agg.update(rec.products_consulted)
        return [{"id": pid, "count": count} for pid, count in agg.most_common(k)]

    async def sweep_expired(self) -> int:
        ttl = get_settings().session_ttl_seconds
        cutoff = time.time() - ttl
        async with self._lock:
            expired = [sid for sid, r in self._store.items() if r.last_seen < cutoff]
            for sid in expired:
                self._store.pop(sid, None)
        if expired:
            logger.info(f"Swept {len(expired)} expired sessions")
        return len(expired)


_store: Optional[SessionStore] = None


def get_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


async def sweeper_loop(interval_seconds: int = 60) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await get_store().sweep_expired()
        except Exception as e:
            logger.exception(f"sweeper_loop error: {e}")
