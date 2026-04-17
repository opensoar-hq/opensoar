"""Microsoft Defender for Endpoint connector.

Uses the Azure AD OAuth 2.0 client-credentials flow to obtain a bearer token
for the Microsoft Defender for Endpoint API (``api.securitycenter.microsoft.com``).
Exposes alert, machine, and indicator operations used by playbooks.
"""
from __future__ import annotations

from typing import Any

import aiohttp

from opensoar.integrations.base import ActionDefinition, HealthCheckResult, IntegrationBase

_API_BASE = "https://api.securitycenter.microsoft.com"
_SCOPE = "https://api.securitycenter.microsoft.com/.default"
_RESOURCE = "https://api.securitycenter.microsoft.com"


class MSDefenderIntegration(IntegrationBase):
    integration_type = "msdefender"
    display_name = "Microsoft Defender for Endpoint"
    description = (
        "Microsoft Defender for Endpoint integration for alerts, machine isolation, "
        "antivirus scans, and threat indicators"
    )

    def __init__(self, config: dict[str, Any]):
        self._client: aiohttp.ClientSession | None = None
        self._access_token: str | None = None
        super().__init__(config)

    # ── config / lifecycle ──────────────────────────────────

    def _validate_config(self, config: dict[str, Any]) -> None:
        for key in ("tenant_id", "client_id", "client_secret"):
            if key not in config or not config[key]:
                raise ValueError(
                    f"Microsoft Defender requires '{key}' in config "
                    f"(provide via environment-backed integration config)"
                )

    async def connect(self) -> None:
        token = await self._fetch_access_token()
        self._access_token = token
        self._client = aiohttp.ClientSession(
            base_url=_API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    async def _fetch_access_token(self) -> str:
        tenant = self._config["tenant_id"]
        token_url = (
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        )
        body = {
            "grant_type": "client_credentials",
            "client_id": self._config["client_id"],
            "client_secret": self._config["client_secret"],
            "scope": _SCOPE,
            "resource": _RESOURCE,
        }
        token_session = aiohttp.ClientSession()
        try:
            async with token_session.post(
                token_url,
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                data = await resp.json()
                if resp.status != 200 or "access_token" not in data:
                    raise RuntimeError(
                        f"Failed to obtain Defender access token: "
                        f"status={resp.status} error={data.get('error', 'unknown')}"
                    )
                return str(data["access_token"])
        finally:
            await token_session.close()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def health_check(self) -> HealthCheckResult:
        if not self._client:
            return HealthCheckResult(healthy=False, message="Not connected")
        try:
            async with self._client.get("/api/alerts", params={"$top": 1}) as resp:
                if resp.status == 200:
                    return HealthCheckResult(healthy=True, message="OK")
                return HealthCheckResult(healthy=False, message=f"HTTP {resp.status}")
        except Exception as e:  # pragma: no cover - exercised via mocking if needed
            return HealthCheckResult(healthy=False, message=str(e))

    # ── actions metadata ────────────────────────────────────

    def get_actions(self) -> list[ActionDefinition]:
        return [
            ActionDefinition(
                name="list_alerts",
                description="List Defender alerts, optionally filtered via OData",
                parameters={
                    "odata_filter": {"type": "string"},
                    "top": {"type": "integer"},
                },
            ),
            ActionDefinition(
                name="get_alert",
                description="Fetch a single Defender alert by ID",
                parameters={"alert_id": {"type": "string"}},
            ),
            ActionDefinition(
                name="isolate_machine",
                description="Isolate a machine from the network",
                parameters={
                    "machine_id": {"type": "string"},
                    "comment": {"type": "string"},
                    "isolation_type": {"type": "string"},
                },
            ),
            ActionDefinition(
                name="unisolate_machine",
                description="Release a machine from isolation",
                parameters={
                    "machine_id": {"type": "string"},
                    "comment": {"type": "string"},
                },
            ),
            ActionDefinition(
                name="list_machines",
                description="List onboarded Defender machines",
                parameters={
                    "odata_filter": {"type": "string"},
                    "top": {"type": "integer"},
                },
            ),
            ActionDefinition(
                name="run_antivirus_scan",
                description="Trigger a Defender antivirus scan on a machine",
                parameters={
                    "machine_id": {"type": "string"},
                    "scan_type": {"type": "string"},
                    "comment": {"type": "string"},
                },
            ),
            ActionDefinition(
                name="list_indicators",
                description="List custom threat indicators configured in Defender",
                parameters={
                    "odata_filter": {"type": "string"},
                    "top": {"type": "integer"},
                },
            ),
        ]

    # ── action implementations ──────────────────────────────

    def _require_client(self) -> aiohttp.ClientSession:
        if not self._client:
            raise RuntimeError("Not connected")
        return self._client

    @staticmethod
    def _build_params(
        odata_filter: str | None, top: int | None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if odata_filter:
            params["$filter"] = odata_filter
        if top is not None:
            params["$top"] = top
        return params

    async def list_alerts(
        self, odata_filter: str | None = None, top: int | None = None
    ) -> list[dict[str, Any]]:
        client = self._require_client()
        params = self._build_params(odata_filter, top)
        async with client.get("/api/alerts", params=params) as resp:
            data = await resp.json()
        return list(data.get("value", []))

    async def get_alert(self, alert_id: str) -> dict[str, Any]:
        client = self._require_client()
        async with client.get(f"/api/alerts/{alert_id}") as resp:
            return await resp.json()

    async def isolate_machine(
        self,
        machine_id: str,
        comment: str = "Isolated by OpenSOAR",
        isolation_type: str = "Full",
    ) -> dict[str, Any]:
        client = self._require_client()
        body = {"Comment": comment, "IsolationType": isolation_type}
        async with client.post(
            f"/api/machines/{machine_id}/isolate", json=body
        ) as resp:
            return await resp.json()

    async def unisolate_machine(
        self, machine_id: str, comment: str = "Unisolated by OpenSOAR"
    ) -> dict[str, Any]:
        client = self._require_client()
        body = {"Comment": comment}
        async with client.post(
            f"/api/machines/{machine_id}/unisolate", json=body
        ) as resp:
            return await resp.json()

    async def list_machines(
        self, odata_filter: str | None = None, top: int | None = None
    ) -> list[dict[str, Any]]:
        client = self._require_client()
        params = self._build_params(odata_filter, top)
        async with client.get("/api/machines", params=params) as resp:
            data = await resp.json()
        return list(data.get("value", []))

    async def run_antivirus_scan(
        self,
        machine_id: str,
        scan_type: str = "Quick",
        comment: str = "AV scan triggered by OpenSOAR",
    ) -> dict[str, Any]:
        client = self._require_client()
        body = {"ScanType": scan_type, "Comment": comment}
        async with client.post(
            f"/api/machines/{machine_id}/runAntiVirusScan", json=body
        ) as resp:
            return await resp.json()

    async def list_indicators(
        self, odata_filter: str | None = None, top: int | None = None
    ) -> list[dict[str, Any]]:
        client = self._require_client()
        params = self._build_params(odata_filter, top)
        async with client.get("/api/indicators", params=params) as resp:
            data = await resp.json()
        return list(data.get("value", []))
