"""Embedding providers (ADR-0007).

Anthropic does not offer an embeddings endpoint, so embeddings are a separate,
abstracted concern:

  * HashingEmbedder — deterministic signed-hashing bag-of-words. No deps, no
    network; captures lexical similarity well enough to make RAG work offline
    and in tests. The default.
  * VoyageEmbedder — Voyage AI (Anthropic's recommended partner) for real
    semantic embeddings when a key is configured.

Both produce EMBEDDING_DIM-length L2-normalized vectors, so cosine similarity is
just a dot product and the pgvector column dimension is fixed.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from app.core.config import get_settings

# Fixed vector dimension. Matches Voyage's voyage-3 output (1024) so the same
# pgvector column works for either provider; switching providers needs a
# re-index (ADR-0004/0007).
EMBEDDING_DIM = 1024

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """Deterministic signed feature-hashing embedder."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    async def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _tokenize(text):
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class VoyageEmbedder:
    """Voyage AI embeddings (optional; requires the `voyageai` package)."""

    def __init__(self, api_key: str, model: str) -> None:
        import voyageai  # lazy; only needed when configured

        self._client = voyageai.AsyncClient(api_key=api_key)
        self._model = model

    async def embed(self, text: str) -> list[float]:
        result = await self._client.embed([text], model=self._model, input_type="query")
        return result.embeddings[0]


def get_embedder() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "voyage" and settings.voyage_api_key:
        return VoyageEmbedder(settings.voyage_api_key, settings.voyage_model)
    return HashingEmbedder()
