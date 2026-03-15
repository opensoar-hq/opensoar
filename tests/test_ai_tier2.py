"""Tests for AI Tier 2 — playbook generation, auto-resolve, LLM correlation."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from opensoar.ai.client import LLMResponse
from opensoar.ai.prompts import build_playbook_prompt, build_auto_resolve_prompt, build_correlation_prompt


class TestPlaybookGeneration:
    def test_playbook_prompt(self):
        """Should build a prompt from natural language description."""
        prompt = build_playbook_prompt(
            "When a critical alert comes in from Elastic with a suspicious IP, "
            "look it up on VirusTotal and AbuseIPDB. If it's malicious, "
            "isolate the host and notify the SOC Slack channel."
        )
        assert "playbook" in prompt.lower()
        assert "@playbook" in prompt or "async def" in prompt

    async def test_generate_endpoint(self, client, registered_analyst):
        """POST /ai/generate-playbook should return Python code."""
        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.complete.return_value = LLMResponse(
                content='''```python
from opensoar.core.decorators import playbook, action
import asyncio

@playbook(trigger="elastic", conditions={"severity": ["critical"]})
async def triage_critical(alert):
    vt, abuse = await asyncio.gather(
        lookup_virustotal(alert.iocs),
        lookup_abuseipdb(alert.source_ip),
    )
    if vt.malicious or abuse.confidence > 80:
        await isolate_host(alert.hostname)
        await notify_slack("#soc-critical", f"Host isolated: {alert.hostname}")
```''',
                model="claude-sonnet-4-20250514",
                usage={},
            )
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/generate-playbook",
                json={
                    "description": "Triage critical Elastic alerts with VT and AbuseIPDB",
                },
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "code" in data
            assert "@playbook" in data["code"] or "async def" in data["code"]


class TestAutoResolve:
    def test_auto_resolve_prompt(self):
        """Should build a prompt for auto-resolve decision."""
        alerts = [
            {"title": "Windows Update Check", "severity": "low", "source_ip": "10.0.0.5"},
            {"title": "Scheduled Task Created", "severity": "low", "source_ip": "10.0.0.5"},
        ]
        prompt = build_auto_resolve_prompt(alerts)
        assert "resolve" in prompt.lower() or "benign" in prompt.lower()
        assert "confidence" in prompt.lower()

    async def test_auto_resolve_endpoint(self, client, registered_analyst, sample_alert_via_api):
        """POST /ai/auto-resolve should return a resolve decision."""
        alert_id = sample_alert_via_api["alert_id"]

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.complete.return_value = LLMResponse(
                content='{"should_resolve": false, "confidence": 0.4, "reasoning": "Alert severity is high, needs analyst review."}',
                model="gpt-4o",
                usage={},
            )
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/auto-resolve",
                json={"alert_ids": [str(alert_id)]},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "results" in data
            assert len(data["results"]) == 1
            assert "should_resolve" in data["results"][0]
            assert "confidence" in data["results"][0]


class TestLLMCorrelation:
    def test_correlation_prompt(self):
        """Should build a prompt for LLM-based alert correlation."""
        alerts = [
            {"title": "Brute Force SSH", "source_ip": "10.0.0.1", "severity": "high"},
            {"title": "Privilege Escalation", "hostname": "web-01", "severity": "critical"},
            {"title": "Data Exfil Detected", "dest_ip": "203.0.113.5", "severity": "critical"},
        ]
        prompt = build_correlation_prompt(alerts)
        assert "correlat" in prompt.lower() or "related" in prompt.lower()
        assert "group" in prompt.lower() or "incident" in prompt.lower()

    async def test_correlate_endpoint(self, client, registered_analyst):
        """POST /ai/correlate should return grouping suggestions."""
        # Create a few alerts
        alert_ids = []
        for i in range(3):
            resp = await client.post(
                "/api/v1/webhooks/alerts",
                json={"rule_name": f"Corr Test {i}", "severity": "high", "source_ip": "10.0.0.99"},
            )
            alert_ids.append(resp.json()["alert_id"])

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.complete.return_value = LLMResponse(
                content='{"groups": [{"title": "Coordinated Attack from 10.0.0.99", "alert_ids": ' + str(alert_ids).replace("'", '"') + ', "reasoning": "All alerts share source IP 10.0.0.99"}]}',
                model="claude-sonnet-4-20250514",
                usage={},
            )
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/correlate",
                json={"alert_ids": [str(a) for a in alert_ids]},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "groups" in data
