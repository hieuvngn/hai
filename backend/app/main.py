"""FastAPI app — lifespan + routers."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .llm import FatalError, warmup_or_die
from .log import configure_logging, logger
from .rag import RagIndex
from .rag.embedder import Embedder
from .routes import admin, cart, chat, orders, public
from .session import sweeper_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    s = get_settings()
    logger.info(f"Starting {s.app_name} (chat_model={s.chat_model}, embed_model={s.embed_model})")
    try:
        await warmup_or_die()
    except FatalError as e:
        logger.error(f"Startup aborted: {e}")
        raise

    try:
        app.state.rag_index = RagIndex.load()
    except FileNotFoundError as e:
        logger.warning(f"{e}. Chạy scripts/generate_dataset.py + scripts/build_embeddings.py.")
        app.state.rag_index = None

    app.state.embedder = Embedder()

    sweeper_task = asyncio.create_task(sweeper_loop(interval_seconds=60))
    # storage sweeper — lazy import so app still boots if storage module not yet present
    storage_sweeper_task = None
    try:
        from .data.storage import storage_sweeper_loop

        storage_sweeper_task = asyncio.create_task(storage_sweeper_loop(interval_seconds=3600))
        logger.info("Storage sweeper started (3600s)")
    except Exception as e:
        logger.warning(f"storage_sweeper_loop not started: {e}")

    logger.info("Startup complete.")
    try:
        yield
    finally:
        sweeper_task.cancel()
        try:
            await sweeper_task
        except asyncio.CancelledError:
            pass
        if storage_sweeper_task is not None:
            storage_sweeper_task.cancel()
            try:
                await storage_sweeper_task
            except asyncio.CancelledError:
                pass
        logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(public.router)
    app.include_router(chat.router)
    app.include_router(admin.router)
    app.include_router(cart.router)
    app.include_router(orders.router)
    return app


app = create_app()
