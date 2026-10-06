"""Embedder — OpenRouter chính, fallback local nếu model không khả dụng."""
from __future__ import annotations

from typing import List

from ..llm import FatalError, TransientError, embed_texts
from ..log import logger


class Embedder:
    """Gọi OpenRouter embeddings; fallback local sentence-transformers nếu fail (429/model lỗi)."""

    def __init__(self) -> None:
        self._local_model = None
        self._local_dim: int | None = None
        self._backend: str = "openrouter"

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            return await embed_texts(texts)
        except (FatalError, TransientError) as e:
            logger.warning(f"OpenRouter embedding fail: {e}. Fallback sang local.")
            return self._embed_local(texts)

    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading local sentence-transformers/all-MiniLM-L6-v2 ...")
            self._local_model = SentenceTransformer("all-MiniLM-L6-v2")
            self._local_dim = self._local_model.get_sentence_embedding_dimension()
            self._backend = "local"
        vectors = self._local_model.encode(
            texts, convert_to_numpy=True, show_progress_bar=False
        )
        return vectors.tolist()

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def dim(self) -> int | None:
        if self._backend == "openrouter":

            return None  # OpenRouter không công bố dim cố định; check runtime
        return self._local_dim
