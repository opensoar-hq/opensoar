"""Tests for AI analyst recommendations — POST /ai/recommend."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from opensoar.ai.client import LLMResponse
from opensoar.ai.prompts import build_recommendation_prompt
from opensoar.schemas.ai import AiRecommendation


class TestRecommendationPrompt:
    def test_recommendation_prompt_includes_alert(self):
        """Prompt should contain the alert data."""
        alert = {
            "title": "Brute Force SSH",
            "severity": "high",
            "source_ip": "10.0.0.1",
            "hostname": "web-01",
        }
        prompt = build_recommendation_prompt(alert, observables=[], similar_alerts=[])
        assert "Brute Force SSH" in prompt
        assert "10.0.0.1" in prompt

    def test_recommendation_prompt_mentions_action_choices(self):
        """Prompt must list the allowed action vocabulary."""
        prompt = build_recommendation_prompt({"title": "x"}, observables=[], similar_alerts=[])
        for action in ("isolate", "block", "enrich", "escalate", "resolve"):
            assert action in prompt

    def test_recommendation_prompt_includes_observables(self):
        """Prompt should embed observable + enrichment context."""
        observables = [
            {
                "type": "ip",
                "value": "203.0.113.5",
                "enrichments": [{"source": "virustotal", "data": {"malicious": 40}}],
            }
        ]
        prompt = build_recommendation_prompt(
            {"title": "x"}, observables=observables, similar_alerts=[]
        )
        assert "203.0.113.5" in prompt
        assert "virustotal" in prompt

    def test_recommendation_prompt_includes_similar_alerts(self):
        """Prompt should embed similar past alerts context."""
        similar = [{"id": "abc", "title": "Prior brute force", "determination": "malicious"}]
        prompt = build_recommendation_prompt(
            {"title": "x"}, observables=[], similar_alerts=similar
        )
        assert "Prior brute force" in prompt
        assert "malicious" in prompt


class TestAiRecommendationSchema:
    def test_valid_action_accepted(self):
        """Schema accepts allowed action values."""
        rec = AiRecommendation(action="isolate", confidence=0.9, reasoning="bad ip")
        assert rec.action == "isolate"
        assert rec.confidence == 0.9

    def test_invalid_action_rejected(self):
        """Schema rejects non-whitelisted action values."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AiRecommendation(action="nuke", confidence=0.5, reasoning="x")

    def test_confidence_bounds_enforced(self):
        """Confidence must be between 0 and 1."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AiRecommendation(action="block", confidence=1.5, reasoning="x")
        with pytest.raises(ValidationError):
            AiRecommendation(action="block", confidence=-0.1, reasoning="x")


class TestRecommendEndpoint:
    async def test_recommend_returns_schema(self, client, sample_alert_via_api, registered_analyst):
        """POST /ai/recommend returns an AiRecommendation-shaped response."""
        alert_id = sample_alert_via_api["alert_id"]

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.complete.return_value = LLMResponse(
                content='{"action": "isolate", "confidence": 0.92, "reasoning": "Source IP seen in prior malicious events."}',
                model="gpt-4o",
                usage={},
            )
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/recommend",
                json={"alert_id": str(alert_id)},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] == "isolate"
            assert data["confidence"] == 0.92
            assert data["reasoning"]

    async def test_recommend_routes_each_action(
        self, client, sample_alert_via_api, registered_analyst
    ):
        """Each allowed action value round-trips through the endpoint."""
        alert_id = sample_alert_via_api["alert_id"]

        for action in ("isolate", "block", "enrich", "escalate", "resolve"):
            with patch("opensoar.api.ai.get_llm_client") as mock_get:
                mock_client = AsyncMock()
                mock_client.complete.return_value = LLMResponse(
                    content=f'{{"action": "{action}", "confidence": 0.7, "reasoning": "test"}}',
                    model="gpt-4o",
                    usage={},
                )
                mock_get.return_value = mock_client

                resp = await client.post(
                    "/api/v1/ai/recommend",
                    json={"alert_id": str(alert_id)},
                    headers=registered_analyst["headers"],
                )
                assert resp.status_code == 200
                assert resp.json()["action"] == action

    async def test_recommend_clamps_confidence_when_out_of_range(
        self, client, sample_alert_via_api, registered_analyst
    ):
        """If the LLM returns a confidence outside [0,1], the endpoint clamps it."""
        alert_id = sample_alert_via_api["alert_id"]

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.complete.return_value = LLMResponse(
                content='{"action": "enrich", "confidence": 1.4, "reasoning": "over"}',
                model="gpt-4o",
                usage={},
            )
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/recommend",
                json={"alert_id": str(alert_id)},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            assert resp.json()["confidence"] == 1.0

    async def test_recommend_parses_confidence_as_percentage(
        self, client, sample_alert_via_api, registered_analyst
    ):
        """A confidence >1 but <=100 is treated as a percentage and scaled."""
        alert_id = sample_alert_via_api["alert_id"]

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.complete.return_value = LLMResponse(
                content='{"action": "block", "confidence": 85, "reasoning": "pct"}',
                model="gpt-4o",
                usage={},
            )
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/recommend",
                json={"alert_id": str(alert_id)},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            assert resp.json()["confidence"] == 0.85

    async def test_recommend_works_with_no_observables(
        self, client, sample_alert_via_api, registered_analyst
    ):
        """Endpoint succeeds when the alert has no linked observables."""
        alert_id = sample_alert_via_api["alert_id"]

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.complete.return_value = LLMResponse(
                content='{"action": "escalate", "confidence": 0.5, "reasoning": "limited context"}',
                model="gpt-4o",
                usage={},
            )
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/recommend",
                json={"alert_id": str(alert_id)},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            assert resp.json()["action"] == "escalate"

    async def test_recommend_fallback_on_malformed_llm_output(
        self, client, sample_alert_via_api, registered_analyst
    ):
        """Non-JSON output from the LLM falls back to a safe escalate recommendation."""
        alert_id = sample_alert_via_api["alert_id"]

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.complete.return_value = LLMResponse(
                content="this is not json at all",
                model="gpt-4o",
                usage={},
            )
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/recommend",
                json={"alert_id": str(alert_id)},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] == "escalate"
            assert data["confidence"] == 0.0
            assert "this is not json" in data["reasoning"]

    async def test_recommend_fallback_on_invalid_action(
        self, client, sample_alert_via_api, registered_analyst
    ):
        """If LLM returns an action outside the vocabulary, fall back to escalate."""
        alert_id = sample_alert_via_api["alert_id"]

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.complete.return_value = LLMResponse(
                content='{"action": "destroy", "confidence": 0.9, "reasoning": "bad action"}',
                model="gpt-4o",
                usage={},
            )
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/recommend",
                json={"alert_id": str(alert_id)},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            assert resp.json()["action"] == "escalate"

    async def test_recommend_503_when_no_llm(self, client, sample_alert_via_api, registered_analyst):
        """Graceful 503 when no LLM is configured."""
        alert_id = sample_alert_via_api["alert_id"]

        with patch("opensoar.api.ai.get_llm_client", return_value=None):
            resp = await client.post(
                "/api/v1/ai/recommend",
                json={"alert_id": str(alert_id)},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 503

    async def test_recommend_404_when_alert_missing(self, client, registered_analyst):
        """Returns 404 when the alert id does not exist."""
        missing_id = str(uuid.uuid4())

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_get.return_value = AsyncMock()
            resp = await client.post(
                "/api/v1/ai/recommend",
                json={"alert_id": missing_id},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 404

    async def test_recommend_requires_ai_use_permission(
        self, client, sample_alert_via_api, db_session_factory
    ):
        """Viewers (without AI_USE) are forbidden."""
        from opensoar.auth.jwt import create_access_token
        from opensoar.models.analyst import Analyst

        alert_id = sample_alert_via_api["alert_id"]
        async with db_session_factory() as sess:
            viewer = Analyst(
                username=f"viewer_{uuid.uuid4().hex[:8]}",
                display_name="Viewer",
                email="viewer@opensoar.app",
                password_hash="x",
                role="viewer",
                is_active=True,
            )
            sess.add(viewer)
            await sess.commit()
            await sess.refresh(viewer)
            token = create_access_token(viewer.id, viewer.username)

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_get.return_value = AsyncMock()
            resp = await client.post(
                "/api/v1/ai/recommend",
                json={"alert_id": str(alert_id)},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403

    async def test_recommend_pulls_similar_alerts_by_source_ip(
        self, client, registered_analyst, db_session_factory
    ):
        """Endpoint surfaces historical alerts that share source_ip into the prompt."""
        # Seed two past alerts that share source_ip with the target alert.
        shared_ip = "192.0.2.231"
        resp1 = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Past malicious", "severity": "high", "source_ip": shared_ip},
        )
        assert resp1.status_code in (200, 201)
        resp2 = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Past suspicious", "severity": "medium", "source_ip": shared_ip},
        )
        assert resp2.status_code in (200, 201)
        target = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Current incident", "severity": "high", "source_ip": shared_ip},
        )
        target_id = target.json()["alert_id"]

        with patch("opensoar.api.ai.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.complete.return_value = LLMResponse(
                content='{"action": "block", "confidence": 0.8, "reasoning": "repeat offender"}',
                model="gpt-4o",
                usage={},
            )
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/recommend",
                json={"alert_id": str(target_id)},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200

            # The prompt passed to the LLM should include the past alerts' titles.
            prompt_used = mock_client.complete.await_args.args[0]
            assert "Past malicious" in prompt_used
            assert "Past suspicious" in prompt_used
            # The target alert's id must not appear in the similar-alerts list.
            similar_section = prompt_used.split("Similar past alerts", 1)[1]
            assert str(target_id) not in similar_section
