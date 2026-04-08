"""Tests for alert CRUD API endpoints."""
from __future__ import annotations

import uuid

from fastapi import HTTPException



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

    async def test_tenant_validator_filters_alert_list(self, client, registered_analyst):
        from opensoar.main import app
        from opensoar.models.alert import Alert
        from opensoar.plugins import register_tenant_access_validator

        alert_a = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Scoped A", "severity": "low", "partner": "acme-corp"},
        )
        alert_b = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Scoped B", "severity": "low", "partner": "globex"},
        )
        assert alert_a.status_code == 200
        assert alert_b.status_code == 200

        async def validator(**kwargs):
            query = kwargs.get("query")
            if query is not None and kwargs["resource_type"] == "alert":
                return query.where(Alert.partner == "acme-corp")
            return None

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            resp = await client.get("/api/v1/alerts", headers=registered_analyst["headers"])
        finally:
            app.state.tenant_access_validators = original_validators

        assert resp.status_code == 200
        assert all(alert["partner"] == "acme-corp" for alert in resp.json()["alerts"])


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

    async def test_tenant_validator_blocks_alert_detail(self, client, registered_analyst):
        from opensoar.main import app
        from opensoar.plugins import register_tenant_access_validator

        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Blocked Detail", "severity": "low", "partner": "globex"},
        )
        alert_id = resp.json()["alert_id"]

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is not None and getattr(resource, "partner", None) == "globex":
                raise HTTPException(status_code=403, detail="Tenant access denied")

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            blocked = await client.get(f"/api/v1/alerts/{alert_id}", headers=registered_analyst["headers"])
        finally:
            app.state.tenant_access_validators = original_validators

        assert blocked.status_code == 403

    async def test_tenant_validator_blocks_alert_runs(self, client, registered_analyst):
        from opensoar.main import app
        from opensoar.plugins import register_tenant_access_validator

        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Blocked Runs", "severity": "low", "partner": "globex"},
        )
        alert_id = resp.json()["alert_id"]

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is not None and getattr(resource, "partner", None) == "globex":
                raise HTTPException(status_code=403, detail="Tenant access denied")

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            blocked = await client.get(f"/api/v1/alerts/{alert_id}/runs", headers=registered_analyst["headers"])
        finally:
            app.state.tenant_access_validators = original_validators

        assert blocked.status_code == 403


class TestAlertIncidents:
    async def test_list_linked_incidents_for_alert(
        self, client, sample_alert_via_api, registered_analyst
    ):
        alert_id = sample_alert_via_api["alert_id"]
        create = await client.post(
            "/api/v1/incidents",
            json={"title": "Linked Incident", "severity": "high"},
            headers=registered_analyst["headers"],
        )
        incident_id = create.json()["id"]

        link = await client.post(
            f"/api/v1/incidents/{incident_id}/alerts",
            json={"alert_id": str(alert_id)},
            headers=registered_analyst["headers"],
        )
        assert link.status_code in (200, 201)

        resp = await client.get(
            f"/api/v1/alerts/{alert_id}/incidents",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        incidents = resp.json()
        assert len(incidents) == 1
        assert incidents[0]["id"] == incident_id
        assert incidents[0]["title"] == "Linked Incident"

    async def test_create_incident_from_alert(
        self, client, sample_alert_via_api, registered_analyst
    ):
        alert_id = sample_alert_via_api["alert_id"]

        resp = await client.post(
            f"/api/v1/alerts/{alert_id}/incidents",
            json={
                "title": "Escalated From Alert",
                "severity": "critical",
                "description": "Created from alert detail workflow",
            },
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 201
        incident = resp.json()
        assert incident["title"] == "Escalated From Alert"
        assert incident["severity"] == "critical"
        assert incident["alert_count"] == 1

        linked = await client.get(
            f"/api/v1/alerts/{alert_id}/incidents",
            headers=registered_analyst["headers"],
        )
        assert linked.status_code == 200
        assert linked.json()[0]["id"] == incident["id"]

    async def test_link_existing_incident_from_alert(
        self, client, sample_alert_via_api, registered_analyst
    ):
        alert_id = sample_alert_via_api["alert_id"]
        create = await client.post(
            "/api/v1/incidents",
            json={"title": "Existing Incident", "severity": "medium"},
            headers=registered_analyst["headers"],
        )
        incident_id = create.json()["id"]

        resp = await client.post(
            f"/api/v1/alerts/{alert_id}/incidents",
            json={"incident_id": incident_id},
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 201
        assert resp.json()["id"] == incident_id
        assert resp.json()["alert_count"] == 1

    async def test_cannot_link_same_incident_twice(
        self, client, sample_alert_via_api, registered_analyst
    ):
        alert_id = sample_alert_via_api["alert_id"]
        create = await client.post(
            "/api/v1/incidents",
            json={"title": "Duplicate Link Incident", "severity": "medium"},
            headers=registered_analyst["headers"],
        )
        incident_id = create.json()["id"]

        first = await client.post(
            f"/api/v1/alerts/{alert_id}/incidents",
            json={"incident_id": incident_id},
            headers=registered_analyst["headers"],
        )
        assert first.status_code == 201

        second = await client.post(
            f"/api/v1/alerts/{alert_id}/incidents",
            json={"incident_id": incident_id},
            headers=registered_analyst["headers"],
        )
        assert second.status_code == 409


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

    async def test_tenant_validator_blocks_alert_update(self, client, registered_analyst):
        from opensoar.main import app
        from opensoar.plugins import register_tenant_access_validator

        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Blocked Update", "severity": "low", "partner": "globex"},
        )
        alert_id = resp.json()["alert_id"]

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is not None and getattr(resource, "partner", None) == "globex":
                raise HTTPException(status_code=403, detail="Tenant access denied")

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            blocked = await client.patch(
                f"/api/v1/alerts/{alert_id}",
                json={"severity": "critical"},
                headers=registered_analyst["headers"],
            )
        finally:
            app.state.tenant_access_validators = original_validators

        assert blocked.status_code == 403


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
