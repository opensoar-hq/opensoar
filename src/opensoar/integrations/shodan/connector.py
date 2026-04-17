"""Shodan integration (issue #79).

Provides host, search, DNS, and account lookups against the Shodan REST API
(https://api.shodan.io). Read operations flow through the shared
``EnrichmentCache`` (issue #67) so repeat lookups skip upstream and respect
a per-source TTL configured in :mod:`opensoar.config`.
"""
from __future__ import annotations

from typing import Any

import aiohttp

from opensoar.core.decorators import action
from opensoar.integrations import cache as _cache_module
from opensoar.integrations.base import ActionDefinition, HealthCheckResult, IntegrationBase

_SOURCE = "shodan"
_BASE_URL = "https://api.shodan.io"


class ShodanIntegration(IntegrationBase):
    integration_type = "shodan"
    display_name = "Shodan"
    description = "Shodan infrastructure enrichment — host info, search, and DNS lookups"

    def __init__(self, config: dict[str, Any]):
        self._client: aiohttp.ClientSession | None = None
        super().__init__(config)

    def _validate_config(self, config: dict[str, Any]) -> None:
        if "api_key" not in config:
            raise ValueError("Shodan requires 'api_key' in config")

    async def connect(self) -> None:
        # Shodan authenticates via the ``key`` query string parameter, not a
        # header — attaching it once here keeps every method call clean.
        self._client = aiohttp.ClientSession(
            base_url=_BASE_URL,
            headers={"Accept": "application/json"},
        )

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def health_check(self) -> HealthCheckResult:
        if not self._client:
            return HealthCheckResult(healthy=False, message="Not connected")

        try:
            async with self._client.get("/api-info", params=self._auth_params()) as resp:
                if resp.status == 200:
                    return HealthCheckResult(healthy=True, message="OK")
                return HealthCheckResult(healthy=False, message=f"HTTP {resp.status}")
        except Exception as e:
            return HealthCheckResult(healthy=False, message=str(e))

    def get_actions(self) -> list[ActionDefinition]:
        return [
            ActionDefinition(
                name="host_info",
                description="Get Shodan host record for an IP",
                parameters={"ip": {"type": "string"}},
            ),
            ActionDefinition(
                name="search",
                description="Run a Shodan search query",
                parameters={"query": {"type": "string"}},
            ),
            ActionDefinition(
                name="dns_resolve",
                description="Resolve a hostname to an IP via Shodan DNS",
                parameters={"domain": {"type": "string"}},
            ),
            ActionDefinition(
                name="dns_reverse",
                description="Reverse-resolve an IP to hostnames via Shodan DNS",
                parameters={"ip": {"type": "string"}},
            ),
            ActionDefinition(
                name="account_profile",
                description="Fetch the authenticated account profile",
            ),
            ActionDefinition(
                name="api_info",
                description="Fetch API plan and quota information",
            ),
        ]

    # ── Public enrichment methods ──────────────────────────────────

    async def host_info(self, ip: str) -> dict:
        self._require_connected()
        return await self._cached_get(
            obs_type="ip",
            cache_value=ip,
            path=f"/shodan/host/{ip}",
        )

    async def search(self, query: str) -> dict:
        self._require_connected()
        return await self._cached_get(
            obs_type="search",
            cache_value=query,
            path="/shodan/host/search",
            extra_params={"query": query},
        )

    async def dns_resolve(self, domain: str) -> dict:
        self._require_connected()
        return await self._cached_get(
            obs_type="domain",
            cache_value=domain,
            path="/dns/resolve",
            extra_params={"hostnames": domain},
        )

    async def dns_reverse(self, ip: str) -> dict:
        self._require_connected()
        return await self._cached_get(
            obs_type="ip_reverse",
            cache_value=ip,
            path="/dns/reverse",
            extra_params={"ips": ip},
        )

    async def account_profile(self) -> dict:
        self._require_connected()
        async with self._client.get(  # type: ignore[union-attr]
            "/account/profile", params=self._auth_params()
        ) as resp:
            return await resp.json()

    async def api_info(self) -> dict:
        self._require_connected()
        async with self._client.get(  # type: ignore[union-attr]
            "/api-info", params=self._auth_params()
        ) as resp:
            return await resp.json()

    # ── Internal helpers ───────────────────────────────────────────

    def _require_connected(self) -> None:
        if not self._client:
            raise RuntimeError("Not connected")

    def _auth_params(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        params = {"key": self._config["api_key"]}
        if extra:
            params.update(extra)
        return params

    async def _cached_get(
        self,
        *,
        obs_type: str,
        cache_value: str,
        path: str,
        extra_params: dict[str, str] | None = None,
    ) -> dict:
        async def _fetch() -> dict:
            async with self._client.get(  # type: ignore[union-attr]
                path, params=self._auth_params(extra_params)
            ) as resp:
                return await resp.json()

        return await _cache_module.get_default_cache().get_or_fetch(
            source=_SOURCE,
            obs_type=obs_type,
            value=cache_value,
            fetcher=_fetch,
            ttl_seconds=_cache_module.default_ttl_for(_SOURCE),
        )


# ── Playbook-exposed action stubs ──────────────────────────────────
# These mirror the VirusTotal / AbuseIPDB pattern — they provide default
# no-op behavior for playbooks when the integration isn't configured.


@action(name="shodan.host_info", timeout=30, retries=2, retry_backoff=2.0)
async def host_info(ip: str) -> dict:
    """Look up an IP on Shodan."""
    return {"ip": ip, "source": "shodan", "note": "Configure Shodan integration for live lookups"}


@action(name="shodan.search", timeout=30, retries=2, retry_backoff=2.0)
async def search(query: str) -> dict:
    """Run a Shodan search query."""
    return {
        "query": query,
        "source": "shodan",
        "note": "Configure Shodan integration for live lookups",
    }


@action(name="shodan.dns_resolve", timeout=30, retries=2, retry_backoff=2.0)
async def dns_resolve(domain: str) -> dict:
    """Resolve a domain via Shodan DNS."""
    return {
        "domain": domain,
        "source": "shodan",
        "note": "Configure Shodan integration for live lookups",
    }


@action(name="shodan.dns_reverse", timeout=30, retries=2, retry_backoff=2.0)
async def dns_reverse(ip: str) -> dict:
    """Reverse-resolve an IP via Shodan DNS."""
    return {"ip": ip, "source": "shodan", "note": "Configure Shodan integration for live lookups"}
