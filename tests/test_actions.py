"""Tests for manual action execution API."""
from __future__ import annotations


class TestActionsAPI:
    async def test_execute_action_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/actions/execute",
            json={
                "action_name": "unknown_action",
                "ioc_type": "ips",
                "ioc_value": "203.0.113.42",
            },
        )
        assert resp.status_code == 401

    async def test_execute_action_with_auth(self, client, registered_analyst):
        resp = await client.post(
            "/api/v1/actions/execute",
            json={
                "action_name": "unknown_action",
                "ioc_type": "ips",
                "ioc_value": "203.0.113.42",
            },
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "failed"
        assert "Unknown action" in payload["error"]
