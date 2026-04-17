"""Splunk integration — search, notable events, and alert ingestion."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from opensoar.integrations.base import ActionDefinition, HealthCheckResult, IntegrationBase
from opensoar.integrations.splunk.normalize import normalize_splunk_notable

_POLL_INTERVAL = 1.0
_POLL_TIMEOUT = 300


class SplunkIntegration(IntegrationBase):
    integration_type = "splunk"
    display_name = "Splunk"
    description = "Splunk Enterprise / ES integration for search, notables, and alert ingestion"

    def __init__(self, config: dict[str, Any]):
        self._client: aiohttp.ClientSession | None = None
        super().__init__(config)

    def _validate_config(self, config: dict[str, Any]) -> None:
        if "url" not in config:
            raise ValueError("Splunk requires 'url' in config")
        has_token = "token" in config
        has_basic = "username" in config and "password" in config
        if not (has_token or has_basic):
            raise ValueError(
                "Splunk requires 'token' or 'username'+'password' in config"
            )

    async def connect(self) -> None:
        headers: dict[str, str] = {"Accept": "application/json"}
        auth: aiohttp.BasicAuth | None = None

        if "token" in self._config:
            headers["Authorization"] = f"Bearer {self._config['token']}"
        else:
            auth = aiohttp.BasicAuth(
                self._config["username"], self._config["password"]
            )

        verify_ssl = bool(self._config.get("verify_ssl", True))
        connector = aiohttp.TCPConnector(ssl=verify_ssl)
        self._client = aiohttp.ClientSession(
            base_url=self._config["url"],
            headers=headers,
            auth=auth,
            connector=connector,
        )

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def health_check(self) -> HealthCheckResult:
        if not self._client:
            return HealthCheckResult(healthy=False, message="Not connected")

        try:
            async with self._client.get(
                "/services/server/info", params={"output_mode": "json"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    version = None
                    entry = (data.get("entry") or [{}])[0]
                    version = (entry.get("content") or {}).get("version")
                    return HealthCheckResult(
                        healthy=True,
                        message="OK",
                        details={"version": version or ""},
                    )
                return HealthCheckResult(healthy=False, message=f"HTTP {resp.status}")
        except Exception as e:  # pragma: no cover - network failure path
            return HealthCheckResult(healthy=False, message=str(e))

    def get_actions(self) -> list[ActionDefinition]:
        return [
            ActionDefinition(
                name="run_search",
                description="Dispatch an SPL search and return results",
                parameters={
                    "spl": {"type": "string"},
                    "earliest": {"type": "string"},
                    "latest": {"type": "string"},
                },
            ),
            ActionDefinition(
                name="list_indexes",
                description="List available Splunk indexes",
                parameters={},
            ),
            ActionDefinition(
                name="ingest_alerts",
                description="Poll a saved search for recent notable events",
                parameters={"saved_search": {"type": "string"}},
            ),
            ActionDefinition(
                name="create_notable_event",
                description="Create a notable event via Splunk Enterprise Security",
                parameters={
                    "rule_name": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {"type": "string"},
                },
            ),
        ]

    # ── SPL search job lifecycle ────────────────────────────

    async def run_search(
        self,
        spl: str,
        earliest: str | None = None,
        latest: str | None = None,
        max_count: int = 1000,
    ) -> dict[str, Any]:
        """Dispatch a search, poll until done, and return results."""
        if not self._client:
            raise RuntimeError("Not connected")

        search = spl if spl.lstrip().startswith("search") else f"search {spl}"
        body: dict[str, Any] = {
            "search": search,
            "output_mode": "json",
            "exec_mode": "normal",
        }
        if earliest:
            body["earliest_time"] = earliest
        if latest:
            body["latest_time"] = latest

        async with self._client.post(
            "/services/search/jobs", data=body
        ) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                raise RuntimeError(f"Search dispatch failed: HTTP {resp.status} {text}")
            data = await resp.json()

        sid = data.get("sid")
        if not sid:
            raise RuntimeError("Splunk did not return a search id")

        await self._wait_for_job(sid)
        results = await self._fetch_job_results(sid, max_count=max_count)
        return {"sid": sid, "results": results}

    async def _wait_for_job(self, sid: str) -> None:
        assert self._client is not None
        elapsed = 0.0
        while elapsed < _POLL_TIMEOUT:
            async with self._client.get(
                f"/services/search/jobs/{sid}", params={"output_mode": "json"}
            ) as resp:
                data = await resp.json()
            entry = (data.get("entry") or [{}])[0]
            content = entry.get("content") or {}
            state = content.get("dispatchState")
            if content.get("isDone"):
                if state and state.upper() == "FAILED":
                    raise RuntimeError(f"Splunk job {sid} dispatchState=FAILED")
                return
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL
        raise RuntimeError(f"Splunk job {sid} did not complete in time")

    async def _fetch_job_results(
        self, sid: str, max_count: int = 1000
    ) -> list[dict[str, Any]]:
        assert self._client is not None
        async with self._client.get(
            f"/services/search/jobs/{sid}/results",
            params={"output_mode": "json", "count": str(max_count)},
        ) as resp:
            data = await resp.json()
        return list(data.get("results") or [])

    # ── Indexes ─────────────────────────────────────────────

    async def list_indexes(self) -> list[dict[str, Any]]:
        if not self._client:
            raise RuntimeError("Not connected")
        async with self._client.get(
            "/services/data/indexes", params={"output_mode": "json", "count": "0"}
        ) as resp:
            data = await resp.json()
        entries = data.get("entry") or []
        return [
            {"name": e.get("name"), "content": e.get("content") or {}}
            for e in entries
        ]

    # ── Ingest alerts via saved search ──────────────────────

    async def ingest_alerts(self, saved_search: str) -> list[dict[str, Any]]:
        """Re-dispatch a saved search and normalize its recent results."""
        if not self._client:
            raise RuntimeError("Not connected")

        # Fetch metadata for the saved search (mostly for validation + SPL recovery)
        path = f"/services/saved/searches/{saved_search}/history"
        async with self._client.get(
            path, params={"output_mode": "json"}
        ) as resp:
            meta = await resp.json()

        # Dispatch the saved search synchronously and collect results
        async with self._client.post(
            f"/services/saved/searches/{saved_search}/dispatch",
            data={"output_mode": "json"},
        ) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                raise RuntimeError(
                    f"Saved search dispatch failed: HTTP {resp.status} {text}"
                )
            data = await resp.json()

        sid = data.get("sid") or _extract_sid_from_history(meta)
        if not sid:
            return []

        await self._wait_for_job(sid)
        rows = await self._fetch_job_results(sid)
        return [normalize_splunk_notable(row) for row in rows]

    # ── Notable event creation (Splunk ES) ──────────────────

    async def create_notable_event(
        self,
        rule_name: str,
        description: str | None = None,
        severity: str = "medium",
        **extra: Any,
    ) -> dict[str, Any]:
        """Create a notable event through the Splunk ES notable_update endpoint."""
        if not self._client:
            raise RuntimeError("Not connected")

        body: dict[str, Any] = {
            "rule_name": rule_name,
            "severity": severity,
            "output_mode": "json",
        }
        if description:
            body["description"] = description
        for k, v in extra.items():
            if v is not None:
                body[k] = v

        async with self._client.post(
            "/services/notable_update", data=body
        ) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise RuntimeError(
                    f"Notable event creation failed: HTTP {resp.status} {text}"
                )
            return await resp.json()


def _extract_sid_from_history(meta: dict[str, Any]) -> str | None:
    entries = meta.get("entry") or []
    for entry in entries:
        sid = (entry.get("content") or {}).get("sid") or entry.get("name")
        if sid:
            return sid
    return None
