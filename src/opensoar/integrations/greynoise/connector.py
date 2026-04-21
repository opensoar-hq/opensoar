"""GreyNoise integration (issue #80).

Connector for the GreyNoise API. Exposes four async methods — ``quick_lookup``,
``context``, ``riot``, and ``gnql`` — all routed through the shared TTL cache
from issue #67 (default 6h, configurable via
``settings.enrichment_cache_ttl_greynoise``).
"""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from opensoar.core.decorators import action
from opensoar.integrations import cache as _cache_module
from opensoar.integrations.base import (
    ActionDefinition,
    HealthCheckResult,
    IntegrationBase,
)

_SOURCE = "greynoise"
_BASE_URL = "https://api.greynoise.io"


class GreyNoiseIntegration(IntegrationBase):
    integration_type = "greynoise"
    display_name = "GreyNoise"
    description = "Internet noise and RIOT classification for IP addresses"

    def __init__(self, config: dict[str, Any]):
        self._client: aiohttp.ClientSession | None = None
        super().__init__(config)

    def _validate_config(self, config: dict[str, Any]) -> None:
        if "api_key" not in config:
            raise ValueError("GreyNoise requires 'api_key' in config")

    async def connect(self) -> None:
        self._client = aiohttp.ClientSession(
            base_url=_BASE_URL,
            headers={
                "key": self._config["api_key"],
                "Accept": "application/json",
            },
        )

    async def health_check(self) -> HealthCheckResult:
        if not self._client:
            return HealthCheckResult(healthy=False, message="Not connected")

        try:
            # /v2/noise/quick/8.8.8.8 is a cheap authenticated call that
            # confirms the API key is accepted by the upstream service.
            async with self._client.get("/v2/noise/quick/8.8.8.8") as resp:
                if resp.status == 200:
                    return HealthCheckResult(healthy=True, message="OK")
                return HealthCheckResult(
                    healthy=False, message=f"HTTP {resp.status}"
                )
        except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as e:  # pragma: no cover - defensive
            return HealthCheckResult(healthy=False, message=str(e))

    def get_actions(self) -> list[ActionDefinition]:
        return [
            ActionDefinition(
                name="quick_lookup",
                description="Fast noise/RIOT classification for an IP",
                parameters={"ip": {"type": "string"}},
            ),
            ActionDefinition(
                name="context",
                description="Full noise context for an IP (metadata, tags, raw_data)",
                parameters={"ip": {"type": "string"}},
            ),
            ActionDefinition(
                name="riot",
                description="RIOT lookup — is this IP a known-benign service?",
                parameters={"ip": {"type": "string"}},
            ),
            ActionDefinition(
                name="gnql",
                description="Run a GNQL query against GreyNoise",
                parameters={"query": {"type": "string"}},
            ),
        ]

    async def quick_lookup(self, ip: str) -> dict:
        if not self._client:
            raise RuntimeError("Not connected")

        async def _fetch() -> dict:
            async with self._client.get(f"/v2/noise/quick/{ip}") as resp:
                return await resp.json()

        return await _cache_module.get_default_cache().get_or_fetch(
            source=_SOURCE,
            obs_type="ip",
            value=f"quick:{ip}",
            fetcher=_fetch,
            ttl_seconds=_cache_module.default_ttl_for(_SOURCE),
        )

    async def context(self, ip: str) -> dict:
        if not self._client:
            raise RuntimeError("Not connected")

        async def _fetch() -> dict:
            async with self._client.get(f"/v2/noise/context/{ip}") as resp:
                return await resp.json()

        return await _cache_module.get_default_cache().get_or_fetch(
            source=_SOURCE,
            obs_type="ip",
            value=f"context:{ip}",
            fetcher=_fetch,
            ttl_seconds=_cache_module.default_ttl_for(_SOURCE),
        )

    async def riot(self, ip: str) -> dict:
        if not self._client:
            raise RuntimeError("Not connected")

        async def _fetch() -> dict:
            async with self._client.get(f"/v2/riot/{ip}") as resp:
                return await resp.json()

        return await _cache_module.get_default_cache().get_or_fetch(
            source=_SOURCE,
            obs_type="ip",
            value=f"riot:{ip}",
            fetcher=_fetch,
            ttl_seconds=_cache_module.default_ttl_for(_SOURCE),
        )

    async def gnql(self, query: str) -> dict:
        if not self._client:
            raise RuntimeError("Not connected")

        async def _fetch() -> dict:
            async with self._client.get(
                "/v2/experimental/gnql", params={"query": query}
            ) as resp:
                return await resp.json()

        return await _cache_module.get_default_cache().get_or_fetch(
            source=_SOURCE,
            obs_type="gnql",
            value=query,
            fetcher=_fetch,
            ttl_seconds=_cache_module.default_ttl_for(_SOURCE),
        )

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()


# ── Playbook action stubs ──────────────────────────────────────────
#
# These are the decorated @action entry points that playbooks invoke. They
# intentionally return a descriptive stub when the integration hasn't been
# configured — mirroring the pattern used by VirusTotal and AbuseIPDB.


@action(name="greynoise.quick_lookup", timeout=30, retries=2, retry_backoff=2.0)
async def quick_lookup(ip: str) -> dict:
    """Quick noise/RIOT classification for an IP on GreyNoise."""
    return {
        "ip": ip,
        "source": "greynoise",
        "note": "Configure GreyNoise integration for live lookups",
    }


@action(name="greynoise.context", timeout=30, retries=2, retry_backoff=2.0)
async def context(ip: str) -> dict:
    """Full noise context for an IP on GreyNoise."""
    return {
        "ip": ip,
        "source": "greynoise",
        "note": "Configure GreyNoise integration for live lookups",
    }


@action(name="greynoise.riot", timeout=30, retries=2, retry_backoff=2.0)
async def riot(ip: str) -> dict:
    """RIOT lookup — identifies known-benign services on GreyNoise."""
    return {
        "ip": ip,
        "source": "greynoise",
        "note": "Configure GreyNoise integration for live lookups",
    }


@action(name="greynoise.gnql", timeout=30, retries=2, retry_backoff=2.0)
async def gnql(query: str) -> dict:
    """Run a GNQL query against GreyNoise."""
    return {
        "query": query,
        "source": "greynoise",
        "note": "Configure GreyNoise integration for live lookups",
    }
