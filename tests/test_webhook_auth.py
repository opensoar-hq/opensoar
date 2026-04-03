"""Tests for webhook endpoint authentication via API key."""
from __future__ import annotations

from fastapi import HTTPException

from opensoar.plugins import register_audit_sink


class TestWebhookAuth:
    """Webhook endpoints should optionally require an API key via X-API-Key header."""

    async def test_webhook_without_key_when_not_required(self, client):
        """When no API keys exist, webhooks should still work (open mode)."""
        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Open Mode Alert", "severity": "low"},
        )
        assert resp.status_code == 200

    async def test_webhook_with_valid_key(self, client, registered_admin):
        """Webhook should accept a valid API key."""
        # Create an API key
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "webhook-key"},
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 201
        api_key = resp.json()["key"]

        # Use it on webhook
        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Authed Alert", "severity": "high"},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Authed Alert"

    async def test_webhook_with_invalid_key(self, client):
        """Webhook should reject an invalid API key."""
        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Bad Key Alert", "severity": "low"},
            headers={"X-API-Key": "soar_invalid_key_12345"},
        )
        assert resp.status_code == 401

    async def test_elastic_webhook_with_valid_key(self, client, registered_admin):
        """Elastic webhook should also accept API keys."""
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "elastic-key"},
            headers=registered_admin["headers"],
        )
        api_key = resp.json()["key"]

        resp = await client.post(
            "/api/v1/webhooks/alerts/elastic",
            json={
                "rule": {"name": "Elastic Authed", "severity": "critical"},
                "_id": "elastic-auth-test",
            },
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 200

    async def test_webhook_updates_last_used(self, client, registered_admin):
        """Using an API key should update its last_used_at timestamp."""
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "track-usage-key"},
            headers=registered_admin["headers"],
        )
        api_key = resp.json()["key"]

        await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Usage Track", "severity": "low"},
            headers={"X-API-Key": api_key},
        )

        # List keys and check last_used_at is set
        resp = await client.get(
            "/api/v1/api-keys",
            headers=registered_admin["headers"],
        )
        keys = resp.json()
        matching = [k for k in keys if k["name"] == "track-usage-key"]
        assert len(matching) == 1
        assert matching[0].get("last_used_at") is not None

    async def test_webhook_validator_can_deny_request(self, client, registered_admin):
        from opensoar.main import app
        from opensoar.plugins import register_api_key_validator

        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "scoped-key"},
            headers=registered_admin["headers"],
        )
        api_key = resp.json()["key"]

        async def validator(*, api_key, request, required_scope):
            raise HTTPException(status_code=403, detail=f"Missing scope: {required_scope}")

        original_validators = list(app.state.api_key_validators)
        app.state.api_key_validators = []
        register_api_key_validator(app, validator)
        try:
            blocked = await client.post(
                "/api/v1/webhooks/alerts",
                json={"rule_name": "Blocked Alert", "severity": "low"},
                headers={"X-API-Key": api_key},
            )
        finally:
            app.state.api_key_validators = original_validators

        assert blocked.status_code == 403
        assert "Missing scope" in blocked.json()["detail"]


class TestApiKeyManagement:
    """Tests for API key CRUD."""

    async def test_create_api_key_requires_admin(self, client, registered_analyst):
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "test-key"},
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 403

    async def test_create_and_list_api_keys(self, client, registered_admin):
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "list-test-key"},
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"].startswith("soar_")
        assert data["prefix"]
        assert data["name"] == "list-test-key"

        resp = await client.get(
            "/api/v1/api-keys",
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 200
        names = [k["name"] for k in resp.json()]
        assert "list-test-key" in names

    async def test_revoke_api_key(self, client, registered_admin):
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "revoke-test"},
            headers=registered_admin["headers"],
        )
        key_id = resp.json()["id"]
        api_key = resp.json()["key"]

        # Revoke
        resp = await client.delete(
            f"/api/v1/api-keys/{key_id}",
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 200

        # Revoked key should fail
        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Revoked Key", "severity": "low"},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 401

    async def test_api_key_actions_emit_audit_events(self, client, registered_admin):
        from opensoar.main import app

        seen = []

        async def sink(event):
            seen.append(event)

        original_sinks = list(app.state.audit_sinks)
        app.state.audit_sinks = []
        register_audit_sink(app, sink)
        try:
            create = await client.post(
                "/api/v1/api-keys",
                json={"name": "audit-key"},
                headers=registered_admin["headers"],
            )
            key_id = create.json()["id"]

            revoke = await client.delete(
                f"/api/v1/api-keys/{key_id}",
                headers=registered_admin["headers"],
            )
        finally:
            app.state.audit_sinks = original_sinks

        assert create.status_code == 201
        assert revoke.status_code == 200
        assert [event.action for event in seen] == ["api_key.created", "api_key.revoked"]
