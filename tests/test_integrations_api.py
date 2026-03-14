"""Tests for integration CRUD and health check endpoints."""
from __future__ import annotations

import uuid


class TestIntegrationCRUD:
    async def test_create_integration(self, client, registered_analyst):
        resp = await client.post(
            "/api/v1/integrations",
            json={
                "integration_type": "virustotal",
                "name": "VT Production",
                "config": {"api_key": "test-vt-key"},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["integration_type"] == "virustotal"
        assert data["name"] == "VT Production"
        assert data["enabled"] is True
        assert data["health_status"] is None

    async def test_list_integrations(self, client):
        resp = await client.get("/api/v1/integrations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_integration(self, client):
        # Create one first
        resp = await client.post(
            "/api/v1/integrations",
            json={
                "integration_type": "slack",
                "name": "Slack SOC",
                "config": {"webhook_url": "https://hooks.slack.com/test"},
            },
        )
        integration_id = resp.json()["id"]

        resp = await client.get(f"/api/v1/integrations/{integration_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Slack SOC"

    async def test_get_nonexistent(self, client):
        resp = await client.get(f"/api/v1/integrations/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_update_integration(self, client):
        resp = await client.post(
            "/api/v1/integrations",
            json={
                "integration_type": "abuseipdb",
                "name": "AbuseIPDB",
                "config": {"api_key": "test"},
            },
        )
        integration_id = resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/integrations/{integration_id}",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    async def test_delete_integration(self, client):
        resp = await client.post(
            "/api/v1/integrations",
            json={
                "integration_type": "email",
                "name": "SMTP",
                "config": {},
            },
        )
        integration_id = resp.json()["id"]

        resp = await client.delete(f"/api/v1/integrations/{integration_id}")
        assert resp.status_code == 200

        resp = await client.get(f"/api/v1/integrations/{integration_id}")
        assert resp.status_code == 404


class TestIntegrationHealthCheck:
    async def test_health_check_unknown_type(self, client):
        """Health check on an integration with unknown type returns an error status."""
        resp = await client.post(
            "/api/v1/integrations",
            json={
                "integration_type": "unknown_vendor",
                "name": "Unknown",
                "config": {},
            },
        )
        integration_id = resp.json()["id"]

        resp = await client.post(f"/api/v1/integrations/{integration_id}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy"] is False
        assert "unknown" in data["message"].lower() or "not supported" in data["message"].lower()

    async def test_health_check_updates_model(self, client):
        """Health check should update health_status and last_health_check on the integration."""
        resp = await client.post(
            "/api/v1/integrations",
            json={
                "integration_type": "unknown_vendor",
                "name": "Health Track",
                "config": {},
            },
        )
        integration_id = resp.json()["id"]

        await client.post(f"/api/v1/integrations/{integration_id}/health")

        resp = await client.get(f"/api/v1/integrations/{integration_id}")
        data = resp.json()
        assert data["health_status"] is not None
        assert data["last_health_check"] is not None

    async def test_health_check_nonexistent(self, client):
        resp = await client.post(f"/api/v1/integrations/{uuid.uuid4()}/health")
        assert resp.status_code == 404
