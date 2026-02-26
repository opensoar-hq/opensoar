from __future__ import annotations

from typing import Any

import aiohttp

from opensoar.integrations.base import ActionDefinition, HealthCheckResult, IntegrationBase


class ElasticIntegration(IntegrationBase):
    integration_type = "elastic"
    display_name = "Elastic Security"
    description = "Elastic Security SIEM integration for alerts, cases, and response actions"

    def __init__(self, config: dict[str, Any]):
        self._client: aiohttp.ClientSession | None = None
        super().__init__(config)

    def _validate_config(self, config: dict[str, Any]) -> None:
        if "url" not in config:
            raise ValueError("Elastic requires 'url' in config")
        if "api_key" not in config and ("username" not in config or "password" not in config):
            raise ValueError("Elastic requires 'api_key' or 'username'+'password' in config")

    async def connect(self) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if "api_key" in self._config:
            headers["Authorization"] = f"ApiKey {self._config['api_key']}"
        else:
            auth = aiohttp.BasicAuth(self._config["username"], self._config["password"])

        self._client = aiohttp.ClientSession(
            base_url=self._config["url"],
            headers=headers,
        )

    async def health_check(self) -> HealthCheckResult:
        if not self._client:
            return HealthCheckResult(healthy=False, message="Not connected")

        try:
            async with self._client.get("/api/status") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return HealthCheckResult(
                        healthy=True,
                        message="Connected",
                        details={"version": data.get("version", {}).get("number")},
                    )
                return HealthCheckResult(healthy=False, message=f"HTTP {resp.status}")
        except Exception as e:
            return HealthCheckResult(healthy=False, message=str(e))

    def get_actions(self) -> list[ActionDefinition]:
        return [
            ActionDefinition(
                name="get_alerts",
                description="Query Elastic Security alerts",
                parameters={"query": {"type": "object"}, "size": {"type": "integer"}},
            ),
            ActionDefinition(
                name="isolate_host",
                description="Isolate a host via Elastic Endpoint",
                parameters={"agent_id": {"type": "string"}},
            ),
            ActionDefinition(
                name="create_case",
                description="Create an Elastic Security case",
                parameters={
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
            ),
        ]

    async def get_alerts(self, query: dict | None = None, size: int = 100) -> dict:
        if not self._client:
            raise RuntimeError("Not connected")

        async with self._client.post(
            "/api/detection_engine/signals/search",
            json={"query": query or {"match_all": {}}, "size": size},
        ) as resp:
            return await resp.json()

    async def isolate_host(self, agent_id: str) -> dict:
        if not self._client:
            raise RuntimeError("Not connected")

        async with self._client.post(
            "/api/endpoint/action/isolate",
            json={"endpoint_ids": [agent_id]},
        ) as resp:
            return await resp.json()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
