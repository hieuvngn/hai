"""Loguru setup — module-wide logger."""
from __future__ import annotations

import sys

from loguru import logger

from .config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <7}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        backtrace=False,
        enqueue=False,
    )
    logger.info(f"Logging configured for app={settings.app_name}")


__all__ = ["logger", "configure_logging"]
