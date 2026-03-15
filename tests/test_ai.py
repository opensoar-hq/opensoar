"""Tests for AI features — LLM client, alert summarization, suggested triage."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from opensoar.ai.client import LLMClient, LLMResponse
from opensoar.ai.prompts import build_summarize_prompt, build_triage_prompt, build_ioc_context_prompt


class TestLLMClient:
    def test_supports_multiple_providers(self):
        """LLMClient should accept different provider configs."""
        client = LLMClient(provider="openai", api_key="test", model="gpt-4o")
        assert client.provider == "openai"

        client = LLMClient(provider="anthropic", api_key="test", model="claude-sonnet-4-20250514")
        assert client.provider == "anthropic"

        client = LLMClient(provider="ollama", base_url="http://localhost:11434", model="llama3")
        assert client.provider == "ollama"

    async def test_complete_returns_response(self):
        """complete() should return an LLMResponse."""
        client = LLMClient(provider="openai", api_key="test", model="gpt-4o")

        mock_response = LLMResponse(
            content="This is a test response",
            model="gpt-4o",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
        )

        with patch.object(client, "_call_provider", new_callable=AsyncMock, return_value=mock_response):
            result = await client.complete("Hello")
            assert result.content == "This is a test response"
            assert result.model == "gpt-4o"

    async def test_complete_with_system_prompt(self):
        """complete() should pass system prompt to provider."""
        client = LLMClient(provider="openai", api_key="test", model="gpt-4o")

        mock_response = LLMResponse(content="response", model="gpt-4o", usage={})

        with patch.object(client, "_call_provider", new_callable=AsyncMock, return_value=mock_response) as mock:
            await client.complete("user msg", system="You are a SOC analyst.")
            mock.assert_awaited_once()
            call_args = mock.call_args
            assert call_args[1]["system"] == "You are a SOC analyst."


class TestPrompts:
    def test_summarize_prompt(self):
        """Should build a summarize prompt from alert data."""
        alert = {
            "title": "Brute Force Detected",
            "severity": "high",
            "source_ip": "10.0.0.1",
            "hostname": "web-01",
            "iocs": {"ips": ["10.0.0.1"]},
            "description": "Multiple failed login attempts detected",
        }
        prompt = build_summarize_prompt(alert)
        assert "Brute Force Detected" in prompt
        assert "10.0.0.1" in prompt
        assert "high" in prompt

    def test_triage_prompt(self):
        """Should build a triage prompt requesting severity + determination."""
        alert = {
            "title": "Suspicious Process",
            "severity": "medium",
            "source_ip": "172.16.0.5",
            "raw_payload": {"process": {"name": "nc"}},
        }
        prompt = build_triage_prompt(alert)
        assert "severity" in prompt.lower()
        assert "determination" in prompt.lower()

    def test_ioc_context_prompt(self):
        """Should build a prompt synthesizing IOC enrichment data."""
        enrichments = [
            {"source": "virustotal", "data": {"malicious": 5, "total": 70}},
            {"source": "abuseipdb", "data": {"confidence_score": 85, "reports": 42}},
        ]
        prompt = build_ioc_context_prompt("ip", "203.0.113.42", enrichments)
        assert "203.0.113.42" in prompt
        assert "virustotal" in prompt
        assert "abuseipdb" in prompt


class TestAIEndpoints:
    async def test_summarize_alert(self, client, sample_alert_via_api, registered_analyst):
        """POST /ai/summarize should return a summary."""
        alert_id = sample_alert_via_api["alert_id"]

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.complete.return_value = LLMResponse(
                content="This alert indicates a brute force attack from 10.0.0.1 targeting web-prod-01.",
                model="gpt-4o",
                usage={"prompt_tokens": 100, "completion_tokens": 30},
            )
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/summarize",
                json={"alert_id": str(alert_id)},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "summary" in data
            assert len(data["summary"]) > 0

    async def test_triage_alert(self, client, sample_alert_via_api, registered_analyst):
        """POST /ai/triage should return suggested severity + determination."""
        alert_id = sample_alert_via_api["alert_id"]

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.complete.return_value = LLMResponse(
                content='{"severity": "high", "determination": "suspicious", "confidence": 0.85, "reasoning": "Brute force pattern from known bad IP."}',
                model="gpt-4o",
                usage={},
            )
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/triage",
                json={"alert_id": str(alert_id)},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "severity" in data
            assert "determination" in data
            assert "confidence" in data

    async def test_ai_disabled_without_config(self, client, registered_analyst):
        """AI endpoints should return 503 when no LLM is configured."""
        with patch("opensoar.api.ai.get_llm_client", return_value=None):
            resp = await client.post(
                "/api/v1/ai/summarize",
                json={"alert_id": "00000000-0000-0000-0000-000000000000"},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 503
