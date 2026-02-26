from __future__ import annotations

from typing import Any

import aiohttp

from opensoar.core.decorators import action
from opensoar.integrations.base import ActionDefinition, HealthCheckResult, IntegrationBase


class VirusTotalIntegration(IntegrationBase):
    integration_type = "virustotal"
    display_name = "VirusTotal"
    description = "File, URL, IP, and domain reputation lookups"

    def __init__(self, config: dict[str, Any]):
        self._client: aiohttp.ClientSession | None = None
        super().__init__(config)

    def _validate_config(self, config: dict[str, Any]) -> None:
        if "api_key" not in config:
            raise ValueError("VirusTotal requires 'api_key' in config")

    async def connect(self) -> None:
        self._client = aiohttp.ClientSession(
            base_url="https://www.virustotal.com/api/v3",
            headers={"x-apikey": self._config["api_key"]},
        )

    async def health_check(self) -> HealthCheckResult:
        if not self._client:
            return HealthCheckResult(healthy=False, message="Not connected")

        try:
            async with self._client.get("/users/me") as resp:
                if resp.status == 200:
                    return HealthCheckResult(healthy=True, message="OK")
                return HealthCheckResult(healthy=False, message=f"HTTP {resp.status}")
        except Exception as e:
            return HealthCheckResult(healthy=False, message=str(e))

    def get_actions(self) -> list[ActionDefinition]:
        return [
            ActionDefinition(
                name="lookup_ip",
                description="Get IP address reputation",
                parameters={"ip": {"type": "string"}},
            ),
            ActionDefinition(
                name="lookup_hash",
                description="Get file hash reputation",
                parameters={"file_hash": {"type": "string"}},
            ),
            ActionDefinition(
                name="lookup_domain",
                description="Get domain reputation",
                parameters={"domain": {"type": "string"}},
            ),
        ]

    async def lookup_ip(self, ip: str) -> dict:
        if not self._client:
            raise RuntimeError("Not connected")
        async with self._client.get(f"/ip_addresses/{ip}") as resp:
            return await resp.json()

    async def lookup_hash(self, file_hash: str) -> dict:
        if not self._client:
            raise RuntimeError("Not connected")
        async with self._client.get(f"/files/{file_hash}") as resp:
            return await resp.json()

    async def lookup_domain(self, domain: str) -> dict:
        if not self._client:
            raise RuntimeError("Not connected")
        async with self._client.get(f"/domains/{domain}") as resp:
            return await resp.json()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()


@action(name="virustotal.lookup_ip", timeout=30, retries=2, retry_backoff=2.0)
async def lookup_ip(ip: str) -> dict:
    """Look up an IP address on VirusTotal."""
    return {"ip": ip, "source": "virustotal", "note": "Configure VT integration for live lookups"}


@action(name="virustotal.lookup_hash", timeout=30, retries=2, retry_backoff=2.0)
async def lookup_hash(file_hash: str) -> dict:
    """Look up a file hash on VirusTotal."""
    return {"hash": file_hash, "source": "virustotal", "note": "Configure VT integration for live lookups"}


@action(name="virustotal.lookup_domain", timeout=30, retries=2, retry_backoff=2.0)
async def lookup_domain(domain: str) -> dict:
    """Look up a domain on VirusTotal."""
    return {"domain": domain, "source": "virustotal", "note": "Configure VT integration for live lookups"}
