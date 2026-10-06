"""Load system prompt từ file."""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_customer_prompt() -> str:
    return (_PROMPTS_DIR / "system_customer.txt").read_text(encoding="utf-8")
