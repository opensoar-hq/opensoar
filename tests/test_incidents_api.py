"""Tests for incident (case) management API."""
from __future__ import annotations

import uuid

from fastapi import HTTPException

from opensoar.plugins import register_tenant_access_validator

class TestIncidentCRUD:
    async def test_create_incident(self, client, registered_analyst):
        resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Coordinated Brute Force Campaign",
                "severity": "high",
                "description": "Multiple hosts targeted by same source IP",
            },
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Coordinated Brute Force Campaign"
        assert data["severity"] == "high"
        assert data["status"] == "open"
        assert data["alert_count"] == 0

    async def test_list_incidents(self, client, registered_analyst):
        # Create one first
        await client.post(
            "/api/v1/incidents",
            json={"title": "List Test", "severity": "low"},
            headers=registered_analyst["headers"],
        )
        resp = await client.get("/api/v1/incidents")
        assert resp.status_code == 200
        data = resp.json()
        assert "incidents" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_get_incident(self, client, registered_analyst):
        resp = await client.post(
            "/api/v1/incidents",
            json={"title": "Get Test", "severity": "medium"},
            headers=registered_analyst["headers"],
        )
        incident_id = resp.json()["id"]

        resp = await client.get(f"/api/v1/incidents/{incident_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Get Test"

    async def test_get_nonexistent(self, client):
        resp = await client.get(f"/api/v1/incidents/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_update_incident(self, client, registered_analyst):
        resp = await client.post(
            "/api/v1/incidents",
            json={"title": "Update Test", "severity": "low"},
            headers=registered_analyst["headers"],
        )
        incident_id = resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/incidents/{incident_id}",
            json={"severity": "critical", "status": "investigating"},
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["severity"] == "critical"
        assert resp.json()["status"] == "investigating"

    async def test_close_incident(self, client, registered_analyst):
        resp = await client.post(
            "/api/v1/incidents",
            json={"title": "Close Test", "severity": "low"},
            headers=registered_analyst["headers"],
        )
        incident_id = resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/incidents/{incident_id}",
            json={"status": "closed"},
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"


class TestIncidentAlertLinking:
    async def test_link_alert_to_incident(self, client, registered_analyst, sample_alert_via_api):
        # Create incident
        resp = await client.post(
            "/api/v1/incidents",
            json={"title": "Link Test", "severity": "high"},
            headers=registered_analyst["headers"],
        )
        incident_id = resp.json()["id"]
        alert_id = sample_alert_via_api["alert_id"]

        # Link alert
        resp = await client.post(
            f"/api/v1/incidents/{incident_id}/alerts",
            json={"alert_id": str(alert_id)},
            headers=registered_analyst["headers"],
        )
        assert resp.status_code in (200, 201)

        # Verify alert count
        resp = await client.get(f"/api/v1/incidents/{incident_id}")
        assert resp.json()["alert_count"] >= 1

    async def test_list_incident_alerts(self, client, registered_analyst, sample_alert_via_api):
        resp = await client.post(
            "/api/v1/incidents",
            json={"title": "List Alerts Test", "severity": "medium"},
            headers=registered_analyst["headers"],
        )
        incident_id = resp.json()["id"]
        alert_id = sample_alert_via_api["alert_id"]

        await client.post(
            f"/api/v1/incidents/{incident_id}/alerts",
            json={"alert_id": str(alert_id)},
            headers=registered_analyst["headers"],
        )

        resp = await client.get(f"/api/v1/incidents/{incident_id}/alerts")
        assert resp.status_code == 200
        alerts = resp.json()
        assert len(alerts) >= 1

    async def test_unlink_alert(self, client, registered_analyst, sample_alert_via_api):
        resp = await client.post(
            "/api/v1/incidents",
            json={"title": "Unlink Test", "severity": "low"},
            headers=registered_analyst["headers"],
        )
        incident_id = resp.json()["id"]
        alert_id = sample_alert_via_api["alert_id"]

        await client.post(
            f"/api/v1/incidents/{incident_id}/alerts",
            json={"alert_id": str(alert_id)},
            headers=registered_analyst["headers"],
        )

        resp = await client.delete(
            f"/api/v1/incidents/{incident_id}/alerts/{alert_id}",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200


class TestIncidentFiltering:
    async def test_filter_by_status(self, client, registered_analyst):
        await client.post(
            "/api/v1/incidents",
            json={"title": "Open Incident", "severity": "low"},
            headers=registered_analyst["headers"],
        )

        resp = await client.get("/api/v1/incidents?status=open")
        assert resp.status_code == 200
        for inc in resp.json()["incidents"]:
            assert inc["status"] == "open"

    async def test_filter_by_severity(self, client, registered_analyst):
        await client.post(
            "/api/v1/incidents",
            json={"title": "Critical Incident", "severity": "critical"},
            headers=registered_analyst["headers"],
        )

        resp = await client.get("/api/v1/incidents?severity=critical")
        assert resp.status_code == 200
        for inc in resp.json()["incidents"]:
            assert inc["severity"] == "critical"

    async def test_tenant_validator_filters_incident_list(self, client, registered_analyst):
        from opensoar.main import app
        from opensoar.models.incident import Incident

        await client.post(
            "/api/v1/incidents",
            json={"title": "Scoped Incident", "severity": "low"},
            headers=registered_analyst["headers"],
        )
        await client.post(
            "/api/v1/incidents",
            json={"title": "Blocked Incident", "severity": "low"},
            headers=registered_analyst["headers"],
        )

        async def validator(**kwargs):
            query = kwargs.get("query")
            if query is not None and kwargs["resource_type"] == "incident":
                return query.where(Incident.title == "Scoped Incident")
            return None

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            resp = await client.get("/api/v1/incidents", headers=registered_analyst["headers"])
        finally:
            app.state.tenant_access_validators = original_validators

        assert resp.status_code == 200
        assert {incident["title"] for incident in resp.json()["incidents"]} == {"Scoped Incident"}

    async def test_tenant_validator_blocks_incident_detail_and_update(self, client, registered_analyst):
        from opensoar.main import app

        create = await client.post(
            "/api/v1/incidents",
            json={"title": "Blocked Incident Detail", "severity": "low"},
            headers=registered_analyst["headers"],
        )
        incident_id = create.json()["id"]

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is not None and getattr(resource, "title", "").startswith("Blocked"):
                raise HTTPException(status_code=403, detail="Tenant access denied")

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            detail = await client.get(f"/api/v1/incidents/{incident_id}", headers=registered_analyst["headers"])
            update = await client.patch(
                f"/api/v1/incidents/{incident_id}",
                json={"severity": "critical"},
                headers=registered_analyst["headers"],
            )
        finally:
            app.state.tenant_access_validators = original_validators

        assert detail.status_code == 403
        assert update.status_code == 403


class TestIncidentActivities:
    async def test_incident_create_adds_activity(self, client, registered_analyst):
        create = await client.post(
            "/api/v1/incidents",
            json={"title": "Activity Create", "severity": "medium"},
            headers=registered_analyst["headers"],
        )
        incident_id = create.json()["id"]

        activities = await client.get(
            f"/api/v1/incidents/{incident_id}/activities",
            headers=registered_analyst["headers"],
        )
        assert activities.status_code == 200
        data = activities.json()
        assert data["total"] >= 1
        assert data["activities"][0]["action"] == "incident_created"

    async def test_incident_status_change_adds_activity(self, client, registered_analyst):
        create = await client.post(
            "/api/v1/incidents",
            json={"title": "Activity Status", "severity": "medium"},
            headers=registered_analyst["headers"],
        )
        incident_id = create.json()["id"]

        update = await client.patch(
            f"/api/v1/incidents/{incident_id}",
            json={"status": "investigating"},
            headers=registered_analyst["headers"],
        )
        assert update.status_code == 200

        activities = await client.get(
            f"/api/v1/incidents/{incident_id}/activities",
            headers=registered_analyst["headers"],
        )
        assert any(activity["action"] == "status_change" for activity in activities.json()["activities"])

    async def test_incident_comment_round_trip(self, client, registered_analyst):
        create = await client.post(
            "/api/v1/incidents",
            json={"title": "Activity Comment", "severity": "medium"},
            headers=registered_analyst["headers"],
        )
        incident_id = create.json()["id"]

        comment = await client.post(
            f"/api/v1/incidents/{incident_id}/comments",
            json={"text": "Need handoff after IOC review"},
            headers=registered_analyst["headers"],
        )
        assert comment.status_code == 200
        comment_id = comment.json()["id"]
        assert comment.json()["action"] == "comment"
        assert comment.json()["detail"] == "Need handoff after IOC review"

        edited = await client.patch(
            f"/api/v1/incidents/{incident_id}/comments/{comment_id}",
            json={"text": "Need handoff after IOC review and containment"},
            headers=registered_analyst["headers"],
        )
        assert edited.status_code == 200
        assert edited.json()["detail"] == "Need handoff after IOC review and containment"
        assert len(edited.json()["metadata_json"]["edit_history"]) == 1

    async def test_incident_link_and_unlink_add_activity(self, client, registered_analyst, sample_alert_via_api):
        create = await client.post(
            "/api/v1/incidents",
            json={"title": "Activity Link", "severity": "medium"},
            headers=registered_analyst["headers"],
        )
        incident_id = create.json()["id"]
        alert_id = sample_alert_via_api["alert_id"]

        link = await client.post(
            f"/api/v1/incidents/{incident_id}/alerts",
            json={"alert_id": str(alert_id)},
            headers=registered_analyst["headers"],
        )
        assert link.status_code in (200, 201)

        unlink = await client.delete(
            f"/api/v1/incidents/{incident_id}/alerts/{alert_id}",
            headers=registered_analyst["headers"],
        )
        assert unlink.status_code == 200

        activities = await client.get(
            f"/api/v1/incidents/{incident_id}/activities",
            headers=registered_analyst["headers"],
        )
        actions = [activity["action"] for activity in activities.json()["activities"]]
        assert "alert_linked" in actions
        assert "alert_unlinked" in actions
