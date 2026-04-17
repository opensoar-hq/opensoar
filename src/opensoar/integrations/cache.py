"""TTL-based enrichment cache for integration adapters (issue #67).

Keeps upstream enrichment API traffic down. Keyed by ``(source, type, value)``;
TTL per source comes from :mod:`opensoar.config`. Integration adapters call
:func:`cached_enrichment` (decorator) or :meth:`EnrichmentCache.get_or_fetch`
(imperative) to wrap upstream calls. A small counter shim records
hits/misses/stores — swap for Prometheus metrics once issue #62 ships.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Protocol

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "opensoar:enrichment:"


class CacheBackend(Protocol):
    """Minimal async KV interface — Redis or in-memory fake both satisfy it."""

    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def delete_prefix(self, prefix: str) -> int: ...


class InMemoryCacheBackend:
    """Deterministic in-memory backend for tests. Not thread-safe."""

    def __init__(self) -> None:
        # key -> (value, expires_at_monotonic)
        self._store: dict[str, tuple[str, float]] = {}
        self._clock_offset: float = 0.0

    def _now(self) -> float:
        return time.monotonic() + self._clock_offset

    def _fast_forward(self, seconds: float) -> None:
        """Test helper — advance the backend's internal clock."""
        self._clock_offset += seconds

    async def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if self._now() >= expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = (value, self._now() + max(0, ttl_seconds))

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def delete_prefix(self, prefix: str) -> int:
        matching = [k for k in self._store if k.startswith(prefix)]
        for k in matching:
            del self._store[k]
        return len(matching)


class RedisCacheBackend:
    """Async Redis backend. Lazily connects on first use."""

    def __init__(self, url: str):
        self._url = url
        self._client: Any | None = None
        self._lock = asyncio.Lock()

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        async with self._lock:
            if self._client is None:
                from redis import asyncio as redis_asyncio

                self._client = redis_asyncio.from_url(
                    self._url, encoding="utf-8", decode_responses=True
                )
        return self._client

    async def get(self, key: str) -> str | None:
        client = await self._ensure_client()
        return await client.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        client = await self._ensure_client()
        # redis-py: ex=<seconds> sets the TTL.
        await client.set(key, value, ex=max(1, ttl_seconds))

    async def delete(self, key: str) -> None:
        client = await self._ensure_client()
        await client.delete(key)

    async def delete_prefix(self, prefix: str) -> int:
        client = await self._ensure_client()
        deleted = 0
        async for key in client.scan_iter(match=f"{prefix}*"):
            await client.delete(key)
            deleted += 1
        return deleted


@dataclass
class CacheMetrics:
    """Lightweight counter shim — increments are also logged at INFO.

    TODO(#62): replace with Prometheus counters when the metrics endpoint lands.
    This class has a stable interface so the swap is a one-liner at
    :func:`get_default_cache`.
    """

    hits: int = 0
    misses: int = 0
    stores: int = 0
    invalidations: int = 0
    by_source: dict[str, dict[str, int]] = field(default_factory=dict)

    def _bump(self, kind: str, source: str) -> None:
        bucket = self.by_source.setdefault(
            source, {"hits": 0, "misses": 0, "stores": 0, "invalidations": 0}
        )
        bucket[kind] = bucket.get(kind, 0) + 1

    def hit(self, source: str) -> None:
        self.hits += 1
        self._bump("hits", source)
        logger.info("enrichment_cache.hit source=%s", source)

    def miss(self, source: str) -> None:
        self.misses += 1
        self._bump("misses", source)
        logger.info("enrichment_cache.miss source=%s", source)

    def store(self, source: str) -> None:
        self.stores += 1
        self._bump("stores", source)
        logger.info("enrichment_cache.store source=%s", source)

    def invalidate(self, source: str, count: int = 1) -> None:
        self.invalidations += count
        self._bump("invalidations", source)
        logger.info("enrichment_cache.invalidate source=%s count=%d", source, count)


# ── Source → TTL lookup ─────────────────────────────────────────────


def default_ttl_for(source: str) -> int:
    """Return per-source TTL (seconds) from settings, else a sensible default."""
    from opensoar.config import settings

    table = {
        "virustotal": getattr(settings, "enrichment_cache_ttl_virustotal", 24 * 3600),
        "abuseipdb": getattr(settings, "enrichment_cache_ttl_abuseipdb", 12 * 3600),
        "greynoise": getattr(settings, "enrichment_cache_ttl_greynoise", 6 * 3600),
    }
    return int(table.get(source, getattr(settings, "enrichment_cache_ttl_default", 3600)))


# ── Cache facade ────────────────────────────────────────────────────


class EnrichmentCache:
    """Facade over any ``CacheBackend``. Handles key layout + JSON codec."""

    def __init__(
        self,
        backend: CacheBackend,
        metrics: CacheMetrics | None = None,
    ) -> None:
        self.backend = backend
        self.metrics = metrics or CacheMetrics()

    def build_key(self, source: str, obs_type: str, value: str) -> str:
        # Hash the value so arbitrarily long / unicode observables still fit.
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]
        return f"{CACHE_KEY_PREFIX}{source}:{obs_type}:{digest}"

    def source_prefix(self, source: str) -> str:
        return f"{CACHE_KEY_PREFIX}{source}:"

    async def get(
        self, source: str, obs_type: str, value: str
    ) -> Any | None:
        raw = await self.backend.get(self.build_key(source, obs_type, value))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "enrichment_cache.decode_failed source=%s type=%s", source, obs_type
            )
            return None

    async def set(
        self,
        source: str,
        obs_type: str,
        value: str,
        payload: Any,
        ttl_seconds: int,
    ) -> None:
        key = self.build_key(source, obs_type, value)
        try:
            encoded = json.dumps(payload, default=str)
        except (TypeError, ValueError):
            logger.warning("enrichment_cache.encode_failed source=%s", source)
            return
        await self.backend.set(key, encoded, ttl_seconds=ttl_seconds)
        self.metrics.store(source)

    async def invalidate(self, source: str, obs_type: str, value: str) -> int:
        await self.backend.delete(self.build_key(source, obs_type, value))
        self.metrics.invalidate(source, 1)
        return 1

    async def invalidate_source(self, source: str) -> int:
        count = await self.backend.delete_prefix(self.source_prefix(source))
        self.metrics.invalidate(source, count)
        return count

    async def get_or_fetch(
        self,
        *,
        source: str,
        obs_type: str,
        value: str,
        fetcher: Callable[[], Awaitable[Any]],
        ttl_seconds: int | None = None,
    ) -> Any:
        cached = await self.get(source, obs_type, value)
        if cached is not None:
            self.metrics.hit(source)
            return cached

        self.metrics.miss(source)
        result = await fetcher()
        ttl = ttl_seconds if ttl_seconds is not None else default_ttl_for(source)
        await self.set(source, obs_type, value, result, ttl_seconds=ttl)
        return result


# ── Default singleton wiring ────────────────────────────────────────

_default_cache: EnrichmentCache | None = None


def get_default_cache() -> EnrichmentCache:
    """Return a process-wide cache. Redis-backed in prod, in-memory otherwise."""
    global _default_cache
    if _default_cache is not None:
        return _default_cache
    try:
        from opensoar.config import settings

        backend: CacheBackend = RedisCacheBackend(settings.redis_url)
    except Exception:  # pragma: no cover - defensive fallback
        logger.exception(
            "enrichment_cache.redis_unavailable falling back to in-memory"
        )
        backend = InMemoryCacheBackend()
    _default_cache = EnrichmentCache(backend=backend)
    return _default_cache


def reset_default_cache() -> None:
    """Reset the module-level singleton. Intended for tests."""
    global _default_cache
    _default_cache = None


# ── Decorator helper ────────────────────────────────────────────────


def cached_enrichment(
    cache: EnrichmentCache | None = None,
    *,
    source: str,
    obs_type: str,
    ttl_seconds: int | None = None,
    value_arg: str | None = None,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Wrap an async fetcher so it consults the enrichment cache.

    The observable ``value`` is inferred from the first positional arg unless
    ``value_arg`` names a kwarg. ``cache`` defaults to
    :func:`get_default_cache` at call time so tests can monkey-patch it.
    """

    def decorator(
        fn: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Awaitable[Any]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if value_arg is not None:
                value = kwargs.get(value_arg)
                if value is None and args:
                    value = args[0]
            elif args:
                value = args[0]
            else:
                # No value to key on — skip cache.
                return await fn(*args, **kwargs)

            active_cache = cache if cache is not None else get_default_cache()

            async def _call() -> Any:
                return await fn(*args, **kwargs)

            return await active_cache.get_or_fetch(
                source=source,
                obs_type=obs_type,
                value=str(value),
                fetcher=_call,
                ttl_seconds=ttl_seconds,
            )

        return wrapper

    return decorator
