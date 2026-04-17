"""Tests for the Splunk integration connector and notable-event normalizer."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opensoar.integrations.splunk.connector import SplunkIntegration
from opensoar.integrations.splunk.normalize import normalize_splunk_notable


# ── Config validation ───────────────────────────────────────


class TestSplunkConfig:
    def test_requires_url(self):
        with pytest.raises(ValueError, match="url"):
            SplunkIntegration({"token": "abc"})

    def test_requires_auth(self):
        with pytest.raises(ValueError, match="token"):
            SplunkIntegration({"url": "https://splunk.example.com:8089"})

    def test_accepts_token(self):
        conn = SplunkIntegration(
            {"url": "https://splunk.example.com:8089", "token": "abc"}
        )
        assert conn.integration_type == "splunk"
        assert conn.display_name == "Splunk"

    def test_accepts_basic_auth(self):
        conn = SplunkIntegration(
            {
                "url": "https://splunk.example.com:8089",
                "username": "admin",
                "password": "changeme",
            }
        )
        assert conn is not None

    def test_rejects_username_without_password(self):
        with pytest.raises(ValueError):
            SplunkIntegration(
                {"url": "https://splunk.example.com:8089", "username": "admin"}
            )


# ── Actions descriptor ──────────────────────────────────────


class TestSplunkActions:
    def test_get_actions_lists_supported(self):
        conn = SplunkIntegration(
            {"url": "https://splunk.example.com:8089", "token": "abc"}
        )
        names = {a.name for a in conn.get_actions()}
        assert "run_search" in names
        assert "list_indexes" in names
        assert "ingest_alerts" in names
        assert "create_notable_event" in names


# ── Helper to build a mock aiohttp response ─────────────────


def _mock_response(status: int = 200, json_data: dict | None = None, text: str = ""):
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.text = AsyncMock(return_value=text)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    return resp


class _MockClient:
    def __init__(self):
        self.get = MagicMock()
        self.post = MagicMock()
        self.close = AsyncMock()


# ── run_search lifecycle ────────────────────────────────────


class TestRunSearch:
    @pytest.mark.asyncio
    async def test_run_search_polls_job_until_done(self):
        conn = SplunkIntegration(
            {"url": "https://splunk.example.com:8089", "token": "abc"}
        )
        mock_client = _MockClient()

        # POST /services/search/jobs → returns sid
        create_resp = _mock_response(
            201, {"sid": "1234.5"}, text="<sid>1234.5</sid>"
        )
        mock_client.post.return_value = create_resp

        # GET /services/search/jobs/{sid} → DONE; then GET results
        status_running = _mock_response(
            200, {"entry": [{"content": {"isDone": False, "dispatchState": "RUNNING"}}]}
        )
        status_done = _mock_response(
            200, {"entry": [{"content": {"isDone": True, "dispatchState": "DONE"}}]}
        )
        results_resp = _mock_response(
            200, {"results": [{"_raw": "hit1"}, {"_raw": "hit2"}]}
        )
        mock_client.get.side_effect = [status_running, status_done, results_resp]

        conn._client = mock_client

        with patch("asyncio.sleep", new=AsyncMock()):
            out = await conn.run_search("search index=main", earliest="-15m")

        assert out["sid"] == "1234.5"
        assert len(out["results"]) == 2
        assert out["results"][0]["_raw"] == "hit1"

        # creation call shape
        post_kwargs = mock_client.post.call_args
        assert "/services/search/jobs" in post_kwargs.args[0]
        body = post_kwargs.kwargs["data"]
        assert body["search"].startswith("search ")
        assert body["output_mode"] == "json"

    @pytest.mark.asyncio
    async def test_run_search_raises_when_not_connected(self):
        conn = SplunkIntegration(
            {"url": "https://splunk.example.com:8089", "token": "abc"}
        )
        with pytest.raises(RuntimeError, match="Not connected"):
            await conn.run_search("search index=main")

    @pytest.mark.asyncio
    async def test_run_search_raises_when_job_fails(self):
        conn = SplunkIntegration(
            {"url": "https://splunk.example.com:8089", "token": "abc"}
        )
        mock_client = _MockClient()
        mock_client.post.return_value = _mock_response(201, {"sid": "9"})
        mock_client.get.return_value = _mock_response(
            200, {"entry": [{"content": {"isDone": True, "dispatchState": "FAILED"}}]}
        )
        conn._client = mock_client

        with pytest.raises(RuntimeError, match="FAILED"):
            await conn.run_search("bad spl")


# ── list_indexes ────────────────────────────────────────────


class TestListIndexes:
    @pytest.mark.asyncio
    async def test_list_indexes_returns_names(self):
        conn = SplunkIntegration(
            {"url": "https://splunk.example.com:8089", "token": "abc"}
        )
        mock_client = _MockClient()
        mock_client.get.return_value = _mock_response(
            200,
            {
                "entry": [
                    {"name": "main", "content": {"totalEventCount": 42}},
                    {"name": "_internal", "content": {"totalEventCount": 1000}},
                ]
            },
        )
        conn._client = mock_client

        indexes = await conn.list_indexes()
        assert "main" in [i["name"] for i in indexes]
        assert "_internal" in [i["name"] for i in indexes]

        url_arg = mock_client.get.call_args.args[0]
        assert "/services/data/indexes" in url_arg


# ── ingest_alerts via saved search ──────────────────────────


class TestIngestAlerts:
    @pytest.mark.asyncio
    async def test_ingest_alerts_returns_normalized_alerts(self):
        conn = SplunkIntegration(
            {"url": "https://splunk.example.com:8089", "token": "abc"}
        )
        mock_client = _MockClient()

        # Mock the saved search history endpoint
        mock_client.get.return_value = _mock_response(
            200,
            {
                "entry": [
                    {
                        "name": "abc-history-1",
                        "content": {
                            "sid": "hist-1",
                            "eventSearch": "search index=notable",
                        },
                    }
                ]
            },
        )
        # Mock the job results endpoint (called afterwards)
        mock_client.post.return_value = _mock_response(201, {"sid": "hist-1"})
        # results fetch
        results = _mock_response(
            200,
            {
                "results": [
                    {
                        "event_id": "n-1",
                        "rule_name": "Brute Force",
                        "severity": "high",
                        "src": "10.0.0.1",
                        "dest": "10.0.0.2",
                        "host": "srv01",
                    }
                ]
            },
        )
        status_done = _mock_response(
            200,
            {"entry": [{"content": {"isDone": True, "dispatchState": "DONE"}}]},
        )
        # The ingest path re-dispatches the saved search then polls + fetches results
        mock_client.get.side_effect = [
            mock_client.get.return_value,  # saved search metadata
            status_done,
            results,
        ]

        conn._client = mock_client
        alerts = await conn.ingest_alerts(saved_search="Notable Alerts")

        assert len(alerts) == 1
        assert alerts[0]["source"] == "splunk"
        assert alerts[0]["severity"] == "high"
        assert alerts[0]["title"] == "Brute Force"
        assert alerts[0]["source_ip"] == "10.0.0.1"


# ── create_notable_event (ES) ───────────────────────────────


class TestCreateNotableEvent:
    @pytest.mark.asyncio
    async def test_create_notable_event_posts_to_es_endpoint(self):
        conn = SplunkIntegration(
            {"url": "https://splunk.example.com:8089", "token": "abc"}
        )
        mock_client = _MockClient()
        mock_client.post.return_value = _mock_response(
            200, {"success": True, "message": "created"}
        )
        conn._client = mock_client

        out = await conn.create_notable_event(
            rule_name="Suspicious Login",
            description="Multiple failed logins",
            severity="high",
            src="10.0.0.5",
        )
        assert out["success"] is True

        url_arg = mock_client.post.call_args.args[0]
        assert "notable_event" in url_arg or "/services/notable_update" in url_arg
        body = mock_client.post.call_args.kwargs["data"]
        assert body["rule_name"] == "Suspicious Login"
        assert body["severity"] == "high"


# ── health_check ────────────────────────────────────────────


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_ok(self):
        conn = SplunkIntegration(
            {"url": "https://splunk.example.com:8089", "token": "abc"}
        )
        mock_client = _MockClient()
        mock_client.get.return_value = _mock_response(
            200,
            {"entry": [{"content": {"version": "9.1.2"}}]},
        )
        conn._client = mock_client

        hc = await conn.health_check()
        assert hc.healthy is True
        assert "9.1.2" in (hc.details or {}).get("version", "")

    @pytest.mark.asyncio
    async def test_health_check_not_connected(self):
        conn = SplunkIntegration(
            {"url": "https://splunk.example.com:8089", "token": "abc"}
        )
        hc = await conn.health_check()
        assert hc.healthy is False


# ── Notable-event normalizer ────────────────────────────────


class TestNormalizeSplunkNotable:
    def test_normalize_minimal(self):
        payload = {
            "rule_name": "Suspicious SSH",
            "severity": "high",
            "src": "192.168.1.10",
            "dest": "10.0.0.1",
            "host": "web01",
            "event_id": "evt-1",
        }
        out = normalize_splunk_notable(payload)
        assert out["source"] == "splunk"
        assert out["source_id"] == "evt-1"
        assert out["title"] == "Suspicious SSH"
        assert out["severity"] == "high"
        assert out["source_ip"] == "192.168.1.10"
        assert out["dest_ip"] == "10.0.0.1"
        assert out["hostname"] == "web01"
        assert out["status"] == "new"

    def test_normalize_webhook_wrapped(self):
        """Splunk webhook wraps the notable inside `result`."""
        payload = {
            "result": {
                "rule_name": "DNS Exfil",
                "urgency": "critical",
                "src_ip": "10.0.0.7",
            },
            "search_name": "ES - DNS Exfil",
        }
        out = normalize_splunk_notable(payload)
        assert out["title"] == "DNS Exfil"
        assert out["severity"] == "critical"
        assert out["source_ip"] == "10.0.0.7"

    def test_normalize_missing_fields_defaults(self):
        out = normalize_splunk_notable({})
        assert out["source"] == "splunk"
        assert out["title"]  # non-empty fallback
        assert out["severity"] in {"critical", "high", "medium", "low"}


# ── Loader registration ─────────────────────────────────────


class TestLoaderRegistration:
    def test_builtin_loader_includes_splunk(self):
        from opensoar.integrations.loader import IntegrationLoader

        loader = IntegrationLoader()
        loader.discover_builtin()
        assert "splunk" in loader.available_types()
        cls = loader.get_connector("splunk")
        assert cls is not None
        assert cls.integration_type == "splunk"
