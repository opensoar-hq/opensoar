"""Tests for the GreyNoise integration (issue #80).

Covers connector config validation, HTTP wiring for each of the four methods
(`quick_lookup`, `context`, `riot`, `gnql`), cache reuse via the shared TTL
cache from #67, action registration, and loader discovery.
"""
from __future__ import annotations

from typing import Any

import pytest

from opensoar.integrations.base import HealthCheckResult
from opensoar.integrations.cache import (
    EnrichmentCache,
    InMemoryCacheBackend,
    default_ttl_for,
)


class _MockResp:
    """Async context manager mimicking an aiohttp response."""

    def __init__(self, payload: Any, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    async def __aenter__(self) -> "_MockResp":
        return self

    async def __aexit__(self, *a: Any) -> None:
        return None

    async def json(self) -> Any:
        return self._payload


class _MockClient:
    """Minimal aiohttp-like client that records calls and returns canned data."""

    def __init__(self, responses: dict[tuple[str, str], Any] | None = None) -> None:
        self._responses = responses or {}
        self.calls: list[tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]] = []

    def _lookup(self, method: str, path: str) -> Any:
        payload = self._responses.get((method, path))
        if payload is None:
            payload = {"path": path, "method": method}
        return payload

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> _MockResp:
        self.calls.append(("GET", path, params, json))
        return _MockResp(self._lookup("GET", path))

    def post(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> _MockResp:
        self.calls.append(("POST", path, params, json))
        return _MockResp(self._lookup("POST", path))


@pytest.fixture
def isolated_cache(monkeypatch):
    """Give each test a fresh in-memory enrichment cache.

    The module-level ``get_default_cache`` is backed by Redis in prod and may
    retain values between process runs. Replacing it keeps cache-sensitive
    tests deterministic.
    """
    from opensoar.integrations import cache as cache_module

    backend = InMemoryCacheBackend()
    cache = EnrichmentCache(backend=backend)
    monkeypatch.setattr(cache_module, "get_default_cache", lambda: cache)
    return cache


class TestGreyNoiseConfig:
    def test_missing_api_key_raises(self):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        with pytest.raises(ValueError, match="api_key"):
            GreyNoiseIntegration({})

    def test_metadata_fields(self):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        assert GreyNoiseIntegration.integration_type == "greynoise"
        assert GreyNoiseIntegration.display_name
        assert GreyNoiseIntegration.description


class TestGreyNoiseActions:
    async def test_get_actions_exposes_four_methods(self):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        integ = GreyNoiseIntegration({"api_key": "gn-test"})
        names = {a.name for a in integ.get_actions()}
        assert {"quick_lookup", "context", "riot", "gnql"}.issubset(names)


class TestGreyNoiseHTTP:
    async def test_quick_lookup_calls_quick_endpoint(self, isolated_cache):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        integ = GreyNoiseIntegration({"api_key": "gn-test"})
        client = _MockClient(
            {("GET", "/v2/noise/quick/1.2.3.4"): {
                "ip": "1.2.3.4",
                "noise": True,
                "riot": False,
                "classification": "malicious",
            }}
        )
        integ._client = client

        result = await integ.quick_lookup("1.2.3.4")
        assert result["noise"] is True
        assert result["classification"] == "malicious"
        assert client.calls[0][:2] == ("GET", "/v2/noise/quick/1.2.3.4")

    async def test_context_calls_context_endpoint(self, isolated_cache):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        integ = GreyNoiseIntegration({"api_key": "gn-test"})
        client = _MockClient(
            {("GET", "/v2/noise/context/9.9.9.9"): {
                "ip": "9.9.9.9",
                "seen": True,
                "classification": "benign",
                "metadata": {"country": "US"},
            }}
        )
        integ._client = client

        result = await integ.context("9.9.9.9")
        assert result["seen"] is True
        assert result["metadata"]["country"] == "US"
        assert client.calls[0][:2] == ("GET", "/v2/noise/context/9.9.9.9")

    async def test_riot_calls_riot_endpoint(self, isolated_cache):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        integ = GreyNoiseIntegration({"api_key": "gn-test"})
        client = _MockClient(
            {("GET", "/v2/riot/8.8.8.8"): {
                "ip": "8.8.8.8",
                "riot": True,
                "name": "Google Public DNS",
                "trust_level": "1",
            }}
        )
        integ._client = client

        result = await integ.riot("8.8.8.8")
        assert result["riot"] is True
        assert result["name"] == "Google Public DNS"
        assert client.calls[0][:2] == ("GET", "/v2/riot/8.8.8.8")

    async def test_gnql_calls_experimental_gnql_endpoint(self, isolated_cache):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        integ = GreyNoiseIntegration({"api_key": "gn-test"})
        client = _MockClient(
            {("GET", "/v2/experimental/gnql"): {
                "count": 2,
                "data": [{"ip": "1.1.1.1"}, {"ip": "2.2.2.2"}],
            }}
        )
        integ._client = client

        result = await integ.gnql('classification:malicious last_seen:1d')
        assert result["count"] == 2
        assert len(result["data"]) == 2
        method, path, params, _ = client.calls[0]
        assert (method, path) == ("GET", "/v2/experimental/gnql")
        assert params and params.get("query") == "classification:malicious last_seen:1d"

    async def test_calls_raise_when_not_connected(self):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        integ = GreyNoiseIntegration({"api_key": "gn-test"})
        with pytest.raises(RuntimeError):
            await integ.quick_lookup("1.2.3.4")
        with pytest.raises(RuntimeError):
            await integ.context("1.2.3.4")
        with pytest.raises(RuntimeError):
            await integ.riot("1.2.3.4")
        with pytest.raises(RuntimeError):
            await integ.gnql("classification:malicious")


class TestGreyNoiseHealthCheck:
    async def test_health_check_unconnected(self):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        integ = GreyNoiseIntegration({"api_key": "gn-test"})
        result = await integ.health_check()
        assert isinstance(result, HealthCheckResult)
        assert result.healthy is False

    async def test_health_check_healthy(self):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        integ = GreyNoiseIntegration({"api_key": "gn-test"})
        integ._client = _MockClient()  # default 200 response
        result = await integ.health_check()
        assert result.healthy is True


class TestGreyNoiseCacheIntegration:
    async def test_quick_lookup_is_cached(self, isolated_cache):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        integ = GreyNoiseIntegration({"api_key": "gn-test"})
        client = _MockClient(
            {("GET", "/v2/noise/quick/1.2.3.4"): {"ip": "1.2.3.4", "noise": True}}
        )
        integ._client = client

        first = await integ.quick_lookup("1.2.3.4")
        second = await integ.quick_lookup("1.2.3.4")
        assert first == second
        assert len(client.calls) == 1

    async def test_context_is_cached_per_ip(self, isolated_cache):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        integ = GreyNoiseIntegration({"api_key": "gn-test"})
        client = _MockClient()
        integ._client = client

        await integ.context("1.1.1.1")
        await integ.context("1.1.1.1")
        await integ.context("2.2.2.2")
        # 2 distinct IPs → 2 upstream calls.
        assert len(client.calls) == 2

    async def test_riot_is_cached(self, isolated_cache):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        integ = GreyNoiseIntegration({"api_key": "gn-test"})
        client = _MockClient()
        integ._client = client

        await integ.riot("8.8.8.8")
        await integ.riot("8.8.8.8")
        assert len(client.calls) == 1

    async def test_gnql_is_cached_per_query(self, isolated_cache):
        from opensoar.integrations.greynoise.connector import GreyNoiseIntegration

        integ = GreyNoiseIntegration({"api_key": "gn-test"})
        client = _MockClient()
        integ._client = client

        await integ.gnql("classification:malicious")
        await integ.gnql("classification:malicious")
        await integ.gnql("classification:benign")
        assert len(client.calls) == 2

    async def test_cache_uses_configured_ttl(self):
        # Smoke test that the settings default is 6h (21600s) per issue #67.
        assert default_ttl_for("greynoise") == 6 * 3600


class TestGreyNoiseLoaderRegistration:
    def test_loader_registers_greynoise(self):
        from opensoar.integrations.loader import IntegrationLoader

        loader = IntegrationLoader()
        loader.discover_builtin()
        types = loader.available_types()
        assert "greynoise" in types
        cls = loader.get_connector("greynoise")
        assert cls is not None
        assert cls.integration_type == "greynoise"


class TestGreyNoisePlaybookActions:
    def test_module_exposes_action_decorators(self):
        """Playbooks need @action-wrapped stubs so triggers can reference them."""
        from opensoar.integrations.greynoise import connector

        for name in ("quick_lookup", "context", "riot", "gnql"):
            assert hasattr(connector, name), (
                f"module-level action '{name}' missing"
            )
