"""Tests for alert CRUD API endpoints."""
from __future__ import annotations

import uuid



class TestListAlerts:
    async def test_list_alerts(self, client, sample_alert_via_api):
        resp = await client.get("/api/v1/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_filter_by_severity(self, client, sample_alert_via_api):
        resp = await client.get("/api/v1/alerts?severity=high")
        assert resp.status_code == 200
        for alert in resp.json()["alerts"]:
            assert alert["severity"] == "high"

    async def test_filter_by_status(self, client, sample_alert_via_api):
        resp = await client.get("/api/v1/alerts?status=new")
        assert resp.status_code == 200
        for alert in resp.json()["alerts"]:
            assert alert["status"] == "new"

    async def test_pagination(self, client, sample_alert_via_api):
        resp = await client.get("/api/v1/alerts?limit=1&offset=0")
        assert resp.status_code == 200
        assert len(resp.json()["alerts"]) <= 1


class TestGetAlert:
    async def test_get_existing_alert(self, client, sample_alert_via_api):
        alert_id = sample_alert_via_api["alert_id"]
        resp = await client.get(f"/api/v1/alerts/{alert_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(alert_id)
        assert "raw_payload" in data

    async def test_get_nonexistent_alert(self, client):
        resp = await client.get(f"/api/v1/alerts/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestUpdateAlert:
    async def test_update_severity(self, client, sample_alert_via_api, registered_analyst):
        alert_id = sample_alert_via_api["alert_id"]
        resp = await client.patch(
            f"/api/v1/alerts/{alert_id}",
            json={"severity": "critical"},
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["severity"] == "critical"

    async def test_update_determination(self, client, sample_alert_via_api, registered_analyst):
        alert_id = sample_alert_via_api["alert_id"]
        resp = await client.patch(
            f"/api/v1/alerts/{alert_id}",
            json={"determination": "malicious"},
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["determination"] == "malicious"

    async def test_invalid_determination(self, client, sample_alert_via_api, registered_analyst):
        alert_id = sample_alert_via_api["alert_id"]
        resp = await client.patch(
            f"/api/v1/alerts/{alert_id}",
            json={"determination": "banana"},
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 422

    async def test_resolve_requires_determination(
        self, client, sample_alert_via_api, registered_analyst
    ):
        alert_id = sample_alert_via_api["alert_id"]
        resp = await client.patch(
            f"/api/v1/alerts/{alert_id}",
            json={"status": "resolved"},
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 422
        assert "determination" in resp.json()["detail"].lower()

    async def test_resolve_with_determination(
        self, client, sample_alert_via_api, registered_analyst
    ):
        alert_id = sample_alert_via_api["alert_id"]
        resp = await client.patch(
            f"/api/v1/alerts/{alert_id}",
            json={"status": "resolved", "determination": "benign"},
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    async def test_update_nonexistent(self, client, registered_analyst):
        resp = await client.patch(
            f"/api/v1/alerts/{uuid.uuid4()}",
            json={"severity": "low"},
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 404


class TestClaimAlert:
    async def test_claim_alert(self, client, sample_alert_via_api, registered_analyst):
        alert_id = sample_alert_via_api["alert_id"]
        resp = await client.post(
            f"/api/v1/alerts/{alert_id}/claim",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_to"] == registered_analyst["analyst"]["id"]
        assert data["status"] == "in_progress"

    async def test_claim_requires_auth(self, client, sample_alert_via_api):
        alert_id = sample_alert_via_api["alert_id"]
        resp = await client.post(f"/api/v1/alerts/{alert_id}/claim")
        assert resp.status_code == 401


class TestDeleteAlert:
    async def test_delete_alert(self, client, sample_alert_via_api):
        alert_id = sample_alert_via_api["alert_id"]
        resp = await client.delete(f"/api/v1/alerts/{alert_id}")
        assert resp.status_code == 200

        resp = await client.get(f"/api/v1/alerts/{alert_id}")
        assert resp.status_code == 404

    async def test_delete_nonexistent(self, client):
        resp = await client.delete(f"/api/v1/alerts/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestBulkOperations:
    async def test_bulk_resolve(self, client, registered_analyst):
        alert_ids = []
        for _ in range(3):
            resp = await client.post(
                "/api/v1/webhooks/alerts",
                json={"rule_name": "Bulk Test", "severity": "low"},
            )
            aid = resp.json()["alert_id"]
            await client.patch(
                f"/api/v1/alerts/{aid}",
                json={"determination": "benign"},
                headers=registered_analyst["headers"],
            )
            alert_ids.append(aid)

        resp = await client.post(
            "/api/v1/alerts/bulk",
            json={
                "alert_ids": alert_ids,
                "action": "resolve",
            },
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 3
        assert data["failed"] == 0

    async def test_bulk_resolve_fails_without_determination(self, client, registered_analyst):
        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "No Det", "severity": "high"},
        )
        alert_id = resp.json()["alert_id"]

        resp = await client.post(
            "/api/v1/alerts/bulk",
            json={
                "alert_ids": [alert_id],
                "action": "resolve",
            },
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["failed"] == 1
