"""Tests for the Shodan integration (issue #79).

Covers connector construction, action surface, HTTP method wiring against a
mocked aiohttp client, and cache behavior (hit/miss/expiry) via the shared
``EnrichmentCache`` from issue #67.
"""
from __future__ import annotations

import pytest

from opensoar.integrations import cache as cache_module
from opensoar.integrations.base import HealthCheckResult
from opensoar.integrations.cache import EnrichmentCache, InMemoryCacheBackend
from opensoar.integrations.shodan.connector import ShodanIntegration


class _MockResp:
    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None

    async def json(self):
        return self._payload


class _MockClient:
    """Collects (path, params) calls and returns canned payloads per path."""

    def __init__(self, responses: dict[str, object]):
        self._responses = responses
        self.calls: list[tuple[str, dict | None]] = []

    def get(self, path: str, params=None):
        self.calls.append((path, params))
        resp = self._responses.get(path, self._responses.get("*", {}))
        if isinstance(resp, tuple):
            payload, status = resp
            return _MockResp(payload, status=status)
        return _MockResp(resp)


@pytest.fixture
def fresh_cache(monkeypatch):
    """Swap the module-level cache for an isolated in-memory one per test."""
    backend = InMemoryCacheBackend()
    cache = EnrichmentCache(backend=backend)
    monkeypatch.setattr(cache_module, "get_default_cache", lambda: cache)
    return cache, backend


class TestShodanConstruction:
    def test_requires_api_key(self):
        with pytest.raises(ValueError):
            ShodanIntegration({})

    def test_integration_metadata(self):
        integ = ShodanIntegration({"api_key": "k"})
        assert integ.integration_type == "shodan"
        assert integ.display_name == "Shodan"
        assert "shodan" in integ.description.lower() or "infrastructure" in integ.description.lower()

    def test_actions_surface_covers_required_methods(self):
        integ = ShodanIntegration({"api_key": "k"})
        names = {a.name for a in integ.get_actions()}
        assert {
            "host_info",
            "search",
            "dns_resolve",
            "dns_reverse",
            "account_profile",
            "api_info",
        }.issubset(names)


class TestShodanHealthCheck:
    async def test_not_connected(self):
        integ = ShodanIntegration({"api_key": "k"})
        result = await integ.health_check()
        assert isinstance(result, HealthCheckResult)
        assert result.healthy is False

    async def test_ok_when_api_info_returns_200(self):
        integ = ShodanIntegration({"api_key": "k"})
        integ._client = _MockClient({"/api-info": {"plan": "dev"}})
        result = await integ.health_check()
        assert result.healthy is True

    async def test_unhealthy_on_non_200(self):
        integ = ShodanIntegration({"api_key": "k"})

        class _Fail:
            def get(self, path, params=None):
                return _MockResp({"error": "unauthorized"}, status=401)

        integ._client = _Fail()
        result = await integ.health_check()
        assert result.healthy is False
        assert "401" in result.message


class TestShodanHostInfo:
    async def test_host_info_hits_correct_path_and_returns_payload(self, fresh_cache):
        integ = ShodanIntegration({"api_key": "k"})
        mock = _MockClient({"/shodan/host/1.2.3.4": {"ip_str": "1.2.3.4", "ports": [22, 80]}})
        integ._client = mock

        result = await integ.host_info("1.2.3.4")

        assert result["ip_str"] == "1.2.3.4"
        assert 22 in result["ports"]
        assert mock.calls[0][0] == "/shodan/host/1.2.3.4"

    async def test_host_info_cache_hit_skips_upstream(self, fresh_cache):
        integ = ShodanIntegration({"api_key": "k"})
        mock = _MockClient({"/shodan/host/1.2.3.4": {"ip_str": "1.2.3.4"}})
        integ._client = mock

        first = await integ.host_info("1.2.3.4")
        second = await integ.host_info("1.2.3.4")

        assert first == second
        assert len(mock.calls) == 1  # second served from cache

    async def test_host_info_cache_miss_after_expiry(self, fresh_cache):
        _, backend = fresh_cache
        integ = ShodanIntegration({"api_key": "k"})
        mock = _MockClient({"/shodan/host/1.2.3.4": {"ip_str": "1.2.3.4"}})
        integ._client = mock

        await integ.host_info("1.2.3.4")
        # Jump past any reasonable TTL.
        backend._fast_forward(48 * 3600)
        await integ.host_info("1.2.3.4")

        assert len(mock.calls) == 2


class TestShodanSearch:
    async def test_search_passes_query_param(self, fresh_cache):
        integ = ShodanIntegration({"api_key": "k"})
        mock = _MockClient({"/shodan/host/search": {"matches": [{"ip_str": "9.9.9.9"}]}})
        integ._client = mock

        result = await integ.search("apache port:80")

        assert result["matches"][0]["ip_str"] == "9.9.9.9"
        path, params = mock.calls[0]
        assert path == "/shodan/host/search"
        assert params is not None
        assert params.get("query") == "apache port:80"

    async def test_search_is_cached_per_query(self, fresh_cache):
        integ = ShodanIntegration({"api_key": "k"})
        mock = _MockClient({"/shodan/host/search": {"matches": []}})
        integ._client = mock

        await integ.search("apache")
        await integ.search("apache")
        await integ.search("nginx")

        # apache repeats → 1 upstream call for "apache" + 1 for "nginx"
        assert len(mock.calls) == 2


class TestShodanDNS:
    async def test_dns_resolve_serializes_hostnames(self, fresh_cache):
        integ = ShodanIntegration({"api_key": "k"})
        mock = _MockClient({"/dns/resolve": {"example.com": "93.184.216.34"}})
        integ._client = mock

        result = await integ.dns_resolve("example.com")

        assert result["example.com"] == "93.184.216.34"
        path, params = mock.calls[0]
        assert path == "/dns/resolve"
        assert params is not None
        assert params.get("hostnames") == "example.com"

    async def test_dns_reverse_serializes_ips(self, fresh_cache):
        integ = ShodanIntegration({"api_key": "k"})
        mock = _MockClient({"/dns/reverse": {"8.8.8.8": ["dns.google"]}})
        integ._client = mock

        result = await integ.dns_reverse("8.8.8.8")

        assert result["8.8.8.8"] == ["dns.google"]
        path, params = mock.calls[0]
        assert path == "/dns/reverse"
        assert params is not None
        assert params.get("ips") == "8.8.8.8"

    async def test_dns_resolve_cache_hit(self, fresh_cache):
        integ = ShodanIntegration({"api_key": "k"})
        mock = _MockClient({"/dns/resolve": {"example.com": "93.184.216.34"}})
        integ._client = mock

        await integ.dns_resolve("example.com")
        await integ.dns_resolve("example.com")

        assert len(mock.calls) == 1


class TestShodanAccountEndpoints:
    async def test_account_profile(self, fresh_cache):
        integ = ShodanIntegration({"api_key": "k"})
        mock = _MockClient({"/account/profile": {"member": True}})
        integ._client = mock

        result = await integ.account_profile()

        assert result["member"] is True
        assert mock.calls[0][0] == "/account/profile"

    async def test_api_info(self, fresh_cache):
        integ = ShodanIntegration({"api_key": "k"})
        mock = _MockClient({"/api-info": {"plan": "dev", "query_credits": 100}})
        integ._client = mock

        result = await integ.api_info()

        assert result["plan"] == "dev"
        assert mock.calls[0][0] == "/api-info"


class TestShodanErrors:
    async def test_host_info_without_connect_raises(self, fresh_cache):
        integ = ShodanIntegration({"api_key": "k"})
        with pytest.raises(RuntimeError):
            await integ.host_info("1.2.3.4")

    async def test_search_without_connect_raises(self, fresh_cache):
        integ = ShodanIntegration({"api_key": "k"})
        with pytest.raises(RuntimeError):
            await integ.search("anything")


class TestShodanCacheConfig:
    def test_default_ttl_24_hours(self):
        from opensoar.integrations.cache import default_ttl_for

        assert default_ttl_for("shodan") == 24 * 3600


class TestShodanLoaderDiscovery:
    def test_loader_discovers_shodan(self):
        from opensoar.integrations.loader import IntegrationLoader

        loader = IntegrationLoader()
        loader.discover_builtin()
        assert "shodan" in loader.available_types()
        cls = loader.get_connector("shodan")
        assert cls is not None
        assert cls.integration_type == "shodan"
