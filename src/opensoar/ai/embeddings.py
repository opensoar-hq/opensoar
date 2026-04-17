"""Embedding client for semantic alert deduplication (issue #81).

Mirrors :mod:`opensoar.ai.client` but emits dense vectors instead of text.
Supports three providers:

- ``openai`` — POST ``/v1/embeddings`` with ``text-embedding-3-small``.
- ``ollama`` — POST ``/api/embeddings`` against a local server.
- ``anthropic`` — reserved for Voyage / future first-party embedding API;
  raises ``NotImplementedError`` for now so callers degrade gracefully.

Graceful degradation: :func:`get_embedding_client` returns ``None`` when no
provider is configured. The ``/ai/deduplicate`` endpoint then returns 503,
matching the existing ``/ai/*`` endpoints.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import aiohttp

from opensoar.config import settings

logger = logging.getLogger(__name__)

DEFAULT_OPENAI_MODEL = "text-embedding-3-small"
DEFAULT_OLLAMA_MODEL = "nomic-embed-text"
DEFAULT_ANTHROPIC_MODEL = "voyage-3"


@dataclass
class EmbeddingResponse:
    vector: list[float]
    model: str


class EmbeddingClient:
    """Unified embedding client for multiple providers."""

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str = "",
        base_url: str = "",
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    async def embed(self, text: str) -> EmbeddingResponse:
        """Return an embedding vector for ``text``."""
        return await self._call_provider(text=text)

    async def _call_provider(self, *, text: str) -> EmbeddingResponse:
        if self.provider == "openai":
            return await self._call_openai(text)
        if self.provider == "ollama":
            return await self._call_ollama(text)
        if self.provider == "anthropic":
            return await self._call_anthropic(text)
        raise ValueError(f"Unknown embedding provider: {self.provider}")

    async def _call_openai(self, text: str) -> EmbeddingResponse:
        url = self.base_url or "https://api.openai.com"
        body: dict[str, Any] = {"model": self.model, "input": text}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{url}/v1/embeddings",
                json=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise RuntimeError(f"OpenAI embedding error: {data}")
                vector = data["data"][0]["embedding"]
                return EmbeddingResponse(
                    vector=list(vector),
                    model=data.get("model", self.model),
                )

    async def _call_ollama(self, text: str) -> EmbeddingResponse:
        url = self.base_url or "http://localhost:11434"
        body: dict[str, Any] = {"model": self.model, "prompt": text}
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{url}/api/embeddings", json=body) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise RuntimeError(f"Ollama embedding error: {data}")
                return EmbeddingResponse(
                    vector=list(data.get("embedding", [])),
                    model=self.model,
                )

    async def _call_anthropic(self, text: str) -> EmbeddingResponse:
        # Anthropic does not yet ship a first-party embeddings endpoint.
        # Voyage AI is their recommended provider but requires a separate key.
        raise NotImplementedError(
            "Anthropic embeddings are not available. Use 'openai' or 'ollama'."
        )


def get_embedding_client() -> EmbeddingClient | None:
    """Build an embedding client from settings, or ``None`` if nothing is set.

    Resolution order:
      1. explicit ``AI_EMBEDDING_PROVIDER`` setting, paired with matching creds
      2. first provider with configured credentials (openai → ollama)
    """
    provider = (getattr(settings, "ai_embedding_provider", None) or "").lower()
    model_override = getattr(settings, "ai_embedding_model", None)

    if provider == "openai":
        if not settings.openai_api_key:
            return None
        return EmbeddingClient(
            provider="openai",
            api_key=settings.openai_api_key,
            model=model_override or DEFAULT_OPENAI_MODEL,
        )
    if provider == "ollama":
        if not settings.ollama_url:
            return None
        return EmbeddingClient(
            provider="ollama",
            base_url=settings.ollama_url,
            model=model_override or DEFAULT_OLLAMA_MODEL,
        )
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            return None
        return EmbeddingClient(
            provider="anthropic",
            api_key=settings.anthropic_api_key,
            model=model_override or DEFAULT_ANTHROPIC_MODEL,
        )

    # Auto-detect: prefer OpenAI, then Ollama.
    if settings.openai_api_key:
        return EmbeddingClient(
            provider="openai",
            api_key=settings.openai_api_key,
            model=model_override or DEFAULT_OPENAI_MODEL,
        )
    if settings.ollama_url:
        return EmbeddingClient(
            provider="ollama",
            base_url=settings.ollama_url,
            model=model_override or DEFAULT_OLLAMA_MODEL,
        )
    return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length dense vectors.

    Returns 0.0 for empty, mismatched-length, or zero-norm inputs so callers
    can safely threshold without guarding every edge case.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))
