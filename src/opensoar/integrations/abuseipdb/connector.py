from __future__ import annotations

from typing import Any

import aiohttp

from opensoar.core.decorators import action
from opensoar.integrations import cache as _cache_module
from opensoar.integrations.base import ActionDefinition, HealthCheckResult, IntegrationBase

_SOURCE = "abuseipdb"


class AbuseIPDBIntegration(IntegrationBase):
    integration_type = "abuseipdb"
    display_name = "AbuseIPDB"
    description = "IP address reputation and abuse reporting"

    def __init__(self, config: dict[str, Any]):
        self._client: aiohttp.ClientSession | None = None
        super().__init__(config)

    def _validate_config(self, config: dict[str, Any]) -> None:
        if "api_key" not in config:
            raise ValueError("AbuseIPDB requires 'api_key' in config")

    async def connect(self) -> None:
        self._client = aiohttp.ClientSession(
            base_url="https://api.abuseipdb.com/api/v2",
            headers={
                "Key": self._config["api_key"],
                "Accept": "application/json",
            },
        )

    async def health_check(self) -> HealthCheckResult:
        if not self._client:
            return HealthCheckResult(healthy=False, message="Not connected")

        try:
            async with self._client.get(
                "/check", params={"ipAddress": "8.8.8.8", "maxAgeInDays": "1"}
            ) as resp:
                if resp.status == 200:
                    return HealthCheckResult(healthy=True, message="OK")
                return HealthCheckResult(healthy=False, message=f"HTTP {resp.status}")
        except Exception as e:
            return HealthCheckResult(healthy=False, message=str(e))

    def get_actions(self) -> list[ActionDefinition]:
        return [
            ActionDefinition(
                name="check_ip",
                description="Check an IP address for abuse reports",
                parameters={"ip": {"type": "string"}, "max_age_days": {"type": "integer"}},
            ),
        ]

    async def check_ip(self, ip: str, max_age_days: int = 90) -> dict:
        if not self._client:
            raise RuntimeError("Not connected")

        async def _fetch() -> dict:
            async with self._client.get(
                "/check", params={"ipAddress": ip, "maxAgeInDays": str(max_age_days)}
            ) as resp:
                return await resp.json()

        # max_age_days is part of the semantic lookup; fold it into the key value.
        cache_value = f"{ip}|maxAgeInDays={max_age_days}"
        return await _cache_module.get_default_cache().get_or_fetch(
            source=_SOURCE,
            obs_type="ip",
            value=cache_value,
            fetcher=_fetch,
            ttl_seconds=_cache_module.default_ttl_for(_SOURCE),
        )

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()


@action(name="abuseipdb.check_ip", timeout=30, retries=2, retry_backoff=2.0)
async def check_ip(ip: str, max_age_days: int = 90) -> dict:
    """Check an IP address on AbuseIPDB."""
    return {"ip": ip, "source": "abuseipdb", "note": "Configure AbuseIPDB integration for live lookups"}
