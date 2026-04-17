"""Tests for the TTL-based enrichment cache (issue #67)."""
from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import HTTPException

from opensoar.integrations.cache import (
    CACHE_KEY_PREFIX,
    CacheMetrics,
    EnrichmentCache,
    InMemoryCacheBackend,
    cached_enrichment,
)
from opensoar.plugins import register_tenant_access_validator


class TestInMemoryCacheBackend:
    async def test_set_then_get_returns_value(self):
        backend = InMemoryCacheBackend()
        await backend.set("k", '{"n": 1}', ttl_seconds=60)
        assert await backend.get("k") == '{"n": 1}'

    async def test_expired_value_returns_none(self):
        backend = InMemoryCacheBackend()
        # Use a zero/negative ttl to force immediate expiry.
        await backend.set("k", '{"n": 1}', ttl_seconds=0)
        # Fast-forward time inside the fake backend.
        backend._fast_forward(1)
        assert await backend.get("k") is None

    async def test_delete_removes_value(self):
        backend = InMemoryCacheBackend()
        await backend.set("k", "v", ttl_seconds=60)
        await backend.delete("k")
        assert await backend.get("k") is None

    async def test_delete_by_prefix(self):
        backend = InMemoryCacheBackend()
        await backend.set("a:x", "1", ttl_seconds=60)
        await backend.set("a:y", "2", ttl_seconds=60)
        await backend.set("b:z", "3", ttl_seconds=60)
        count = await backend.delete_prefix("a:")
        assert count == 2
        assert await backend.get("a:x") is None
        assert await backend.get("a:y") is None
        assert await backend.get("b:z") == "3"


class TestEnrichmentCacheCore:
    async def test_cache_miss_calls_upstream_and_stores(self):
        backend = InMemoryCacheBackend()
        metrics = CacheMetrics()
        cache = EnrichmentCache(backend=backend, metrics=metrics)

        upstream = AsyncMock(return_value={"verdict": "clean"})
        result = await cache.get_or_fetch(
            source="virustotal",
            obs_type="ip",
            value="1.2.3.4",
            fetcher=upstream,
            ttl_seconds=60,
        )
        assert result == {"verdict": "clean"}
        upstream.assert_awaited_once()
        assert metrics.misses == 1
        assert metrics.hits == 0
        assert metrics.stores == 1

    async def test_cache_hit_skips_upstream(self):
        backend = InMemoryCacheBackend()
        metrics = CacheMetrics()
        cache = EnrichmentCache(backend=backend, metrics=metrics)

        upstream = AsyncMock(return_value={"verdict": "clean"})
        await cache.get_or_fetch(
            source="virustotal",
            obs_type="ip",
            value="1.2.3.4",
            fetcher=upstream,
            ttl_seconds=60,
        )

        upstream2 = AsyncMock(return_value={"verdict": "should-not-be-used"})
        result = await cache.get_or_fetch(
            source="virustotal",
            obs_type="ip",
            value="1.2.3.4",
            fetcher=upstream2,
            ttl_seconds=60,
        )
        assert result == {"verdict": "clean"}
        upstream2.assert_not_awaited()
        assert metrics.hits == 1

    async def test_ttl_expiry_refetches(self):
        backend = InMemoryCacheBackend()
        metrics = CacheMetrics()
        cache = EnrichmentCache(backend=backend, metrics=metrics)

        call_count = 0

        async def fetcher():
            nonlocal call_count
            call_count += 1
            return {"call": call_count}

        first = await cache.get_or_fetch(
            source="virustotal", obs_type="ip", value="1.2.3.4",
            fetcher=fetcher, ttl_seconds=60,
        )
        assert first == {"call": 1}

        # Expire the entry.
        backend._fast_forward(120)

        second = await cache.get_or_fetch(
            source="virustotal", obs_type="ip", value="1.2.3.4",
            fetcher=fetcher, ttl_seconds=60,
        )
        assert second == {"call": 2}
        assert metrics.misses == 2
        assert metrics.stores == 2

    async def test_invalidate_clears_single_key(self):
        backend = InMemoryCacheBackend()
        cache = EnrichmentCache(backend=backend)

        await cache.set("virustotal", "ip", "1.2.3.4", {"v": 1}, ttl_seconds=60)
        assert await cache.get("virustotal", "ip", "1.2.3.4") == {"v": 1}

        await cache.invalidate("virustotal", "ip", "1.2.3.4")
        assert await cache.get("virustotal", "ip", "1.2.3.4") is None

    async def test_invalidate_by_source_clears_all_matching(self):
        backend = InMemoryCacheBackend()
        cache = EnrichmentCache(backend=backend)

        await cache.set("virustotal", "ip", "1.2.3.4", {"v": 1}, ttl_seconds=60)
        await cache.set("virustotal", "domain", "evil.com", {"v": 2}, ttl_seconds=60)
        await cache.set("abuseipdb", "ip", "1.2.3.4", {"v": 3}, ttl_seconds=60)

        cleared = await cache.invalidate_source("virustotal")
        assert cleared == 2
        assert await cache.get("virustotal", "ip", "1.2.3.4") is None
        assert await cache.get("virustotal", "domain", "evil.com") is None
        assert await cache.get("abuseipdb", "ip", "1.2.3.4") == {"v": 3}

    async def test_key_is_tuple_based(self):
        backend = InMemoryCacheBackend()
        cache = EnrichmentCache(backend=backend)
        key = cache.build_key("virustotal", "ip", "1.2.3.4")
        assert key.startswith(CACHE_KEY_PREFIX)
        assert "virustotal" in key
        assert "ip" in key
        # Different values produce different keys (value is hashed for key safety).
        other = cache.build_key("virustotal", "ip", "5.6.7.8")
        assert key != other

    async def test_cached_enrichment_decorator_wraps_fetcher(self):
        backend = InMemoryCacheBackend()
        cache = EnrichmentCache(backend=backend)

        calls = 0

        @cached_enrichment(cache, source="virustotal", obs_type="ip", ttl_seconds=60)
        async def fetch(ip: str):
            nonlocal calls
            calls += 1
            return {"ip": ip, "score": 0.5}

        r1 = await fetch("1.2.3.4")
        r2 = await fetch("1.2.3.4")
        assert r1 == r2 == {"ip": "1.2.3.4", "score": 0.5}
        assert calls == 1

        r3 = await fetch("5.6.7.8")
        assert calls == 2
        assert r3 == {"ip": "5.6.7.8", "score": 0.5}


class TestIntegrationAdaptersUseCache:
    async def test_virustotal_lookup_ip_uses_cache(self, monkeypatch):
        """VT's lookup_ip should write-through to cache and skip upstream on hit."""
        from opensoar.integrations import cache as cache_module
        from opensoar.integrations.virustotal.connector import VirusTotalIntegration

        backend = InMemoryCacheBackend()
        cache = EnrichmentCache(backend=backend)
        monkeypatch.setattr(cache_module, "get_default_cache", lambda: cache)

        integ = VirusTotalIntegration({"api_key": "test-key"})

        # Replace the HTTP client with a mock that counts calls and returns a canned payload.
        calls = {"n": 0}

        class _MockResp:
            def __init__(self, payload):
                self._payload = payload
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return None
            async def json(self):
                return self._payload

        class _MockClient:
            def get(self, path):
                calls["n"] += 1
                return _MockResp({"data": {"id": path, "score": 1}})

        integ._client = _MockClient()

        first = await integ.lookup_ip("1.2.3.4")
        second = await integ.lookup_ip("1.2.3.4")
        assert first == second
        assert calls["n"] == 1  # second call hit cache

    async def test_abuseipdb_check_ip_uses_cache(self, monkeypatch):
        from opensoar.integrations import cache as cache_module
        from opensoar.integrations.abuseipdb.connector import AbuseIPDBIntegration

        backend = InMemoryCacheBackend()
        cache = EnrichmentCache(backend=backend)
        monkeypatch.setattr(cache_module, "get_default_cache", lambda: cache)

        integ = AbuseIPDBIntegration({"api_key": "abuse-key"})

        calls = {"n": 0}

        class _MockResp:
            def __init__(self, payload):
                self._payload = payload
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return None
            async def json(self):
                return self._payload

        class _MockClient:
            def get(self, path, params=None):
                calls["n"] += 1
                return _MockResp({"data": {"abuseConfidenceScore": 12}})

        integ._client = _MockClient()

        first = await integ.check_ip("1.2.3.4")
        second = await integ.check_ip("1.2.3.4")
        assert first == second
        assert calls["n"] == 1


class TestInvalidationEndpoint:
    async def test_delete_enrichment_by_source_clears_cache_and_record(
        self, client, registered_analyst, monkeypatch
    ):
        from opensoar.integrations import cache as cache_module

        backend = InMemoryCacheBackend()
        cache = EnrichmentCache(backend=backend)
        monkeypatch.setattr(cache_module, "get_default_cache", lambda: cache)

        # Create observable, seed enrichment + cache.
        create = await client.post(
            "/api/v1/observables",
            json={"type": "ip", "value": "203.0.113.55", "source": "cache-test"},
            headers=registered_analyst["headers"],
        )
        obs_id = create.json()["id"]

        await client.post(
            f"/api/v1/observables/{obs_id}/enrichments",
            json={
                "source": "virustotal",
                "data": {"malicious": 2},
                "malicious": False,
                "score": 0.3,
            },
            headers=registered_analyst["headers"],
        )
        await cache.set("virustotal", "ip", "203.0.113.55", {"cached": True}, ttl_seconds=60)
        assert await cache.get("virustotal", "ip", "203.0.113.55") == {"cached": True}

        resp = await client.delete(
            f"/api/v1/observables/{obs_id}/enrichments/virustotal",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["source"] == "virustotal"
        assert payload["cache_cleared"] >= 1

        # Cache entry should now be gone.
        assert await cache.get("virustotal", "ip", "203.0.113.55") is None

        # Observable should no longer have a VT enrichment entry.
        detail = await client.get(
            f"/api/v1/observables/{obs_id}", headers=registered_analyst["headers"]
        )
        enrichments = detail.json()["enrichments"] or []
        assert all(e.get("source") != "virustotal" for e in enrichments)

    async def test_delete_enrichment_requires_auth(self, client, registered_analyst):
        create = await client.post(
            "/api/v1/observables",
            json={"type": "ip", "value": "203.0.113.60", "source": "auth-test"},
            headers=registered_analyst["headers"],
        )
        obs_id = create.json()["id"]

        resp = await client.delete(
            f"/api/v1/observables/{obs_id}/enrichments/virustotal"
        )
        assert resp.status_code == 401

    async def test_delete_enrichment_missing_observable_returns_404(
        self, client, registered_analyst
    ):
        import uuid as _uuid
        resp = await client.delete(
            f"/api/v1/observables/{_uuid.uuid4()}/enrichments/virustotal",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 404

    async def test_delete_enrichment_respects_tenant_scope(
        self, client, registered_analyst, monkeypatch
    ):
        """Tenant validator must be consulted before invalidation proceeds."""
        from opensoar.integrations import cache as cache_module
        from opensoar.main import app

        backend = InMemoryCacheBackend()
        cache = EnrichmentCache(backend=backend)
        monkeypatch.setattr(cache_module, "get_default_cache", lambda: cache)

        create = await client.post(
            "/api/v1/observables",
            json={"type": "ip", "value": "198.51.100.99", "source": "tenant-test"},
            headers=registered_analyst["headers"],
        )
        obs_id = create.json()["id"]

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is not None and getattr(resource, "value", None) == "198.51.100.99":
                raise HTTPException(status_code=403, detail="Tenant access denied")

        original = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            resp = await client.delete(
                f"/api/v1/observables/{obs_id}/enrichments/virustotal",
                headers=registered_analyst["headers"],
            )
        finally:
            app.state.tenant_access_validators = original

        assert resp.status_code == 403
