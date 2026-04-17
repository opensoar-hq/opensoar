"""Tests for the Microsoft Defender for Endpoint integration."""
from __future__ import annotations

from typing import Any

import pytest

from opensoar.integrations.loader import IntegrationLoader
from opensoar.integrations.msdefender.connector import MSDefenderIntegration
from opensoar.integrations.msdefender.normalize import normalize_msdefender_alert


# ── Mock HTTP plumbing ──────────────────────────────────────


class _MockResp:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    async def __aenter__(self) -> "_MockResp":
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def json(self) -> Any:
        return self._payload


class _MockClient:
    """Records every request and returns canned responses keyed by (method, path)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responses: dict[tuple[str, str], tuple[Any, int]] = {}
        self.closed = False

    def set_response(
        self,
        method: str,
        path: str,
        payload: Any,
        status: int = 200,
    ) -> None:
        self.responses[(method.upper(), path)] = (payload, status)

    def _record(self, method: str, path: str, **kwargs: Any) -> _MockResp:
        self.calls.append({"method": method, "path": path, **kwargs})
        payload, status = self.responses.get(
            (method.upper(), path),
            ({"value": []}, 200),
        )
        return _MockResp(payload, status)

    def get(self, path: str, **kwargs: Any) -> _MockResp:
        return self._record("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> _MockResp:
        return self._record("POST", path, **kwargs)

    async def close(self) -> None:
        self.closed = True


# ── Config validation + loader discovery ────────────────────


class TestConfigValidation:
    def test_missing_tenant_raises(self) -> None:
        with pytest.raises(ValueError, match="tenant_id"):
            MSDefenderIntegration({"client_id": "a", "client_secret": "b"})

    def test_missing_client_id_raises(self) -> None:
        with pytest.raises(ValueError, match="client_id"):
            MSDefenderIntegration({"tenant_id": "t", "client_secret": "b"})

    def test_missing_client_secret_raises(self) -> None:
        with pytest.raises(ValueError, match="client_secret"):
            MSDefenderIntegration({"tenant_id": "t", "client_id": "a"})

    def test_valid_config(self) -> None:
        integ = MSDefenderIntegration(
            {"tenant_id": "t", "client_id": "a", "client_secret": "b"},
        )
        assert integ.integration_type == "msdefender"
        assert integ.display_name == "Microsoft Defender for Endpoint"


class TestLoaderDiscovery:
    def test_loader_discovers_msdefender(self) -> None:
        loader = IntegrationLoader()
        loader.discover_builtin()
        assert "msdefender" in loader.available_types()
        cls = loader.get_connector("msdefender")
        assert cls is not None
        assert cls.integration_type == "msdefender"


# ── OAuth token exchange ────────────────────────────────────


class TestAuthTokenExchange:
    async def test_connect_exchanges_client_credentials_for_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """connect() must POST to the tenant's OAuth token endpoint and cache the token."""
        import opensoar.integrations.msdefender.connector as conn_mod

        captured: dict[str, Any] = {}

        class _TokenResp:
            status = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def json(self):
                return {"access_token": "tok-123", "expires_in": 3600}

        class _TokenSession:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured["session_args"] = (args, kwargs)

            def post(self, url: str, data: Any = None, **kwargs: Any) -> _TokenResp:
                captured["token_url"] = url
                captured["token_body"] = data
                return _TokenResp()

            async def close(self) -> None:
                captured["token_closed"] = True

        class _ApiSession:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured["api_args"] = (args, kwargs)

            async def close(self) -> None:
                pass

        calls = {"n": 0}

        def _session_factory(*args: Any, **kwargs: Any):
            calls["n"] += 1
            # First ClientSession is for token exchange; second is the API client.
            return _TokenSession(*args, **kwargs) if calls["n"] == 1 else _ApiSession(*args, **kwargs)

        monkeypatch.setattr(conn_mod.aiohttp, "ClientSession", _session_factory)

        integ = MSDefenderIntegration(
            {"tenant_id": "my-tenant", "client_id": "cid", "client_secret": "sec"},
        )
        await integ.connect()

        assert "my-tenant" in captured["token_url"]
        assert "oauth2" in captured["token_url"]
        body = captured["token_body"]
        assert body["grant_type"] == "client_credentials"
        assert body["client_id"] == "cid"
        assert body["client_secret"] == "sec"
        assert "securitycenter" in body["scope"] or "api.securitycenter" in body["resource"]
        assert integ._access_token == "tok-123"
        # Access token should be set on API session headers via base_url + headers kwargs.
        api_kwargs = captured["api_args"][1]
        assert api_kwargs["headers"]["Authorization"] == "Bearer tok-123"

    async def test_connect_raises_when_token_endpoint_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import opensoar.integrations.msdefender.connector as conn_mod

        class _ErrResp:
            status = 401

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def json(self):
                return {"error": "invalid_client"}

        class _Session:
            def __init__(self, *a, **kw):
                pass

            def post(self, url: str, data: Any = None, **kwargs: Any) -> _ErrResp:
                return _ErrResp()

            async def close(self) -> None:
                pass

        monkeypatch.setattr(conn_mod.aiohttp, "ClientSession", _Session)

        integ = MSDefenderIntegration(
            {"tenant_id": "t", "client_id": "a", "client_secret": "b"},
        )
        with pytest.raises(RuntimeError, match="token"):
            await integ.connect()


# ── Method behavior (uses an injected mock client) ──────────


def _prep(integ: MSDefenderIntegration) -> _MockClient:
    """Attach a mock aiohttp-like client to an already-constructed integration."""
    mock = _MockClient()
    integ._client = mock  # type: ignore[assignment]
    integ._access_token = "tok"
    return mock


def _make() -> MSDefenderIntegration:
    return MSDefenderIntegration(
        {"tenant_id": "t", "client_id": "cid", "client_secret": "sec"},
    )


class TestListAlerts:
    async def test_hits_alerts_endpoint(self) -> None:
        integ = _make()
        mock = _prep(integ)
        mock.set_response("GET", "/api/alerts", {"value": [{"id": "a1"}]})
        result = await integ.list_alerts()
        assert result == [{"id": "a1"}]
        assert mock.calls[0]["method"] == "GET"
        assert mock.calls[0]["path"] == "/api/alerts"

    async def test_passes_odata_filter(self) -> None:
        integ = _make()
        mock = _prep(integ)
        mock.set_response("GET", "/api/alerts", {"value": []})
        await integ.list_alerts(odata_filter="status eq 'New'", top=50)
        params = mock.calls[0]["params"]
        assert params["$filter"] == "status eq 'New'"
        assert params["$top"] == 50

    async def test_requires_connection(self) -> None:
        integ = _make()
        with pytest.raises(RuntimeError, match="Not connected"):
            await integ.list_alerts()


class TestGetAlert:
    async def test_fetches_single_alert_by_id(self) -> None:
        integ = _make()
        mock = _prep(integ)
        mock.set_response("GET", "/api/alerts/abc-1", {"id": "abc-1", "severity": "High"})
        result = await integ.get_alert("abc-1")
        assert result["id"] == "abc-1"
        assert mock.calls[0]["path"] == "/api/alerts/abc-1"


class TestIsolateMachine:
    async def test_posts_to_isolate_endpoint(self) -> None:
        integ = _make()
        mock = _prep(integ)
        mock.set_response(
            "POST", "/api/machines/m-1/isolate", {"id": "act-1", "status": "Pending"}
        )
        result = await integ.isolate_machine("m-1", comment="playbook", isolation_type="Full")
        assert result["id"] == "act-1"
        call = mock.calls[0]
        assert call["method"] == "POST"
        assert call["path"] == "/api/machines/m-1/isolate"
        assert call["json"]["Comment"] == "playbook"
        assert call["json"]["IsolationType"] == "Full"


class TestUnisolateMachine:
    async def test_posts_to_unisolate_endpoint(self) -> None:
        integ = _make()
        mock = _prep(integ)
        mock.set_response("POST", "/api/machines/m-2/unisolate", {"id": "act-2"})
        result = await integ.unisolate_machine("m-2", comment="resolved")
        assert result["id"] == "act-2"
        assert mock.calls[0]["path"] == "/api/machines/m-2/unisolate"
        assert mock.calls[0]["json"]["Comment"] == "resolved"


class TestListMachines:
    async def test_returns_value_array(self) -> None:
        integ = _make()
        mock = _prep(integ)
        mock.set_response(
            "GET",
            "/api/machines",
            {"value": [{"id": "m-1"}, {"id": "m-2"}]},
        )
        result = await integ.list_machines()
        assert len(result) == 2
        assert result[0]["id"] == "m-1"

    async def test_filter_and_top(self) -> None:
        integ = _make()
        mock = _prep(integ)
        mock.set_response("GET", "/api/machines", {"value": []})
        await integ.list_machines(odata_filter="riskScore eq 'High'", top=25)
        params = mock.calls[0]["params"]
        assert params["$filter"] == "riskScore eq 'High'"
        assert params["$top"] == 25


class TestRunAntivirusScan:
    async def test_posts_to_run_av_scan(self) -> None:
        integ = _make()
        mock = _prep(integ)
        mock.set_response(
            "POST", "/api/machines/m-3/runAntiVirusScan", {"id": "act-av-1"}
        )
        result = await integ.run_antivirus_scan("m-3", scan_type="Quick", comment="triage")
        assert result["id"] == "act-av-1"
        call = mock.calls[0]
        assert call["method"] == "POST"
        assert call["path"] == "/api/machines/m-3/runAntiVirusScan"
        assert call["json"]["ScanType"] == "Quick"
        assert call["json"]["Comment"] == "triage"


class TestListIndicators:
    async def test_returns_indicator_list(self) -> None:
        integ = _make()
        mock = _prep(integ)
        mock.set_response(
            "GET",
            "/api/indicators",
            {"value": [{"id": "i-1", "indicatorValue": "1.2.3.4"}]},
        )
        result = await integ.list_indicators()
        assert result == [{"id": "i-1", "indicatorValue": "1.2.3.4"}]
        assert mock.calls[0]["path"] == "/api/indicators"


class TestDisconnect:
    async def test_disconnect_closes_client(self) -> None:
        integ = _make()
        mock = _prep(integ)
        await integ.disconnect()
        assert mock.closed is True


class TestGetActions:
    def test_exposes_all_methods_as_actions(self) -> None:
        integ = _make()
        names = {a.name for a in integ.get_actions()}
        assert {
            "list_alerts",
            "get_alert",
            "isolate_machine",
            "unisolate_machine",
            "list_machines",
            "run_antivirus_scan",
            "list_indicators",
        }.issubset(names)


class TestHealthCheck:
    async def test_healthy_when_alerts_endpoint_200(self) -> None:
        integ = _make()
        mock = _prep(integ)
        mock.set_response("GET", "/api/alerts", {"value": []})
        result = await integ.health_check()
        assert result.healthy is True

    async def test_unhealthy_when_not_connected(self) -> None:
        integ = _make()
        integ._client = None
        result = await integ.health_check()
        assert result.healthy is False


# ── Webhook normalizer ──────────────────────────────────────


class TestNormalizer:
    def test_basic_defender_alert(self) -> None:
        payload = {
            "id": "da-1",
            "title": "Suspicious PowerShell",
            "description": "Encoded command executed",
            "severity": "High",
            "status": "New",
            "computerDnsName": "HOST-01",
            "machineId": "m-abc",
            "category": "Execution",
            "detectionSource": "WindowsDefenderAv",
        }
        result = normalize_msdefender_alert(payload)
        assert result["source"] == "msdefender"
        assert result["source_id"] == "da-1"
        assert result["title"] == "Suspicious PowerShell"
        assert result["severity"] == "high"
        assert result["hostname"] == "HOST-01"
        assert result["rule_name"] == "Suspicious PowerShell"
        assert "Execution" in result.get("tags", [])

    def test_severity_normalized_from_informational(self) -> None:
        payload = {"id": "x", "title": "Info", "severity": "Informational"}
        result = normalize_msdefender_alert(payload)
        assert result["severity"] == "low"

    def test_extracts_iocs_from_evidence(self) -> None:
        payload = {
            "id": "da-2",
            "title": "C2 Beacon",
            "severity": "Medium",
            "evidence": [
                {"entityType": "Ip", "ipAddress": "203.0.113.9"},
                {"entityType": "File", "sha256": "a" * 64},
                {"entityType": "Url", "url": "http://evil.example.com/a"},
            ],
        }
        result = normalize_msdefender_alert(payload)
        iocs = result["iocs"]
        assert "203.0.113.9" in iocs.get("ips", [])
        assert ("a" * 64) in iocs.get("hashes", [])
        # Domain or URL depending on extractor. Accept either.
        assert (
            "evil.example.com" in iocs.get("domains", [])
            or "http://evil.example.com/a" in iocs.get("urls", [])
        )

    def test_falls_back_on_missing_title(self) -> None:
        payload = {"id": "x", "severity": "Low"}
        result = normalize_msdefender_alert(payload)
        assert result["title"]  # non-empty fallback
        assert result["source"] == "msdefender"

    def test_handles_alert_wrapper(self) -> None:
        payload = {
            "alert": {
                "id": "nested-1",
                "title": "Nested alert",
                "severity": "Critical",
            }
        }
        result = normalize_msdefender_alert(payload)
        assert result["source_id"] == "nested-1"
        assert result["severity"] == "critical"
