"""Config loaded from .env via pydantic-settings.

Dựng một `Settings` tốn ~0.9 ms (đọc lại + validate toàn bộ file), nên kết quả được
cache và chỉ dựng lại khi `.env` thay đổi trên đĩa. `stat()` chỉ ~1 µs, nên "sửa .env
không cần restart" vẫn đúng. Khác biệt duy nhất so với cách đọc mỗi lần: biến môi
trường của tiến trình (`os.environ`) được đọc ở lần dựng đầu tiên, sửa sau đó không
 có hiệu lực nếu `.env` không đổi.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Path:
    here = Path(__file__).resolve().parent
    for ancestor in [here, *here.parents]:
        candidate = ancestor / ".env"
        if candidate.is_file():
            return candidate
    return here.parent.parent / ".env"


_ENV_FILE = _find_env_file()

_DEFAULT_CORS = "http://localhost:5173,http://localhost:3000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # OpenRouter
    openrouter_api_key: str = ""
    base_url: str = "https://openrouter.ai/api/v1"
    chat_model: str = "inclusionai/ling-3.0-flash-fin:free"
    embed_model: str = "nvidia/llama-nemotron-embed-vl-1b-v2:free"

    # App
    session_ttl_seconds: int = 1800
    app_name: str = "tokenrouter-fashion-chatbot"
    http_referer: str = "http://localhost:5173"
    x_title: str = "Fashion Sales Chatbot"

    # Admin
    admin_token: str = "change-me"

    # CORS — để raw str, validator sẽ split CSV.
    cors_origins_raw: str = _DEFAULT_CORS

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    @field_validator("cors_origins_raw", mode="before")
    @classmethod
    def _coerce_cors(cls, v):
        if isinstance(v, list):
            return ",".join(str(x) for x in v)
        return v


_cache: Optional[Tuple[Tuple[float, int], Settings]] = None


def get_settings() -> Settings:
    """Instance đã parse; dựng lại khi `.env` đổi trên đĩa.

    Gọi ở hot path — `_build_client` mỗi lần gọi LLM, `require_admin` mỗi request
    admin — nên parse lại file mỗi lần là chi phí vô ích.
    """
    global _cache
    try:
        st = _ENV_FILE.stat()
    except OSError:
        stamp: Tuple[float, int] = (0.0, 0)
    else:
        stamp = (st.st_mtime, st.st_size)
    cached = _cache
    if cached is not None and cached[0] == stamp:
        return cached[1]
    settings = Settings()
    _cache = (stamp, settings)
    return settings
