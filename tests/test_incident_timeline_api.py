"""Tests for aggregated incident timeline API (GET /incidents/{id}/timeline)."""
from __future__ import annotations

import uuid

from fastapi import HTTPException

from opensoar.plugins import register_tenant_access_validator


async def _create_incident(client, headers, title="Timeline Incident", severity="medium"):
    resp = await client.post(
        "/api/v1/incidents",
        json={"title": title, "severity": severity},
        headers=headers,
    )
    return resp.json()["id"]


async def _create_alert(client, rule_name="Timeline Alert", partner="acme-corp"):
    resp = await client.post(
        "/api/v1/webhooks/alerts",
        json={
            "rule_name": rule_name,
            "severity": "high",
            "source_ip": "10.0.0.9",
            "partner": partner,
        },
    )
    return resp.json()["alert_id"]


async def _link(client, headers, incident_id, alert_id):
    await client.post(
        f"/api/v1/incidents/{incident_id}/alerts",
        json={"alert_id": str(alert_id)},
        headers=headers,
    )


class TestIncidentTimelineBasics:
    async def test_timeline_endpoint_exists(self, client, registered_analyst):
        incident_id = await _create_incident(client, registered_analyst["headers"])

        resp = await client.get(
            f"/api/v1/incidents/{incident_id}/timeline",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "events" in body
        assert "total" in body

    async def test_timeline_returns_404_for_missing_incident(self, client, registered_analyst):
        resp = await client.get(
            f"/api/v1/incidents/{uuid.uuid4()}/timeline",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 404

    async def test_timeline_requires_auth_when_tenant_validator_blocks(self, client, registered_analyst):
        from opensoar.main import app

        incident_id = await _create_incident(client, registered_analyst["headers"], title="Blocked Timeline")

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is not None and getattr(resource, "title", "").startswith("Blocked"):
                raise HTTPException(status_code=403, detail="Tenant access denied")

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            resp = await client.get(
                f"/api/v1/incidents/{incident_id}/timeline",
                headers=registered_analyst["headers"],
            )
        finally:
            app.state.tenant_access_validators = original_validators

        assert resp.status_code == 403


class TestIncidentTimelineAggregation:
    async def test_timeline_merges_alert_and_incident_activities(self, client, registered_analyst):
        incident_id = await _create_incident(client, registered_analyst["headers"])
        alert_id = await _create_alert(client)
        await _link(client, registered_analyst["headers"], incident_id, alert_id)

        # Add an alert-side comment
        await client.post(
            f"/api/v1/alerts/{alert_id}/comments",
            json={"text": "Alert-level comment"},
            headers=registered_analyst["headers"],
        )
        # Add an incident-side comment
        await client.post(
            f"/api/v1/incidents/{incident_id}/comments",
            json={"text": "Incident-level comment"},
            headers=registered_analyst["headers"],
        )

        resp = await client.get(
            f"/api/v1/incidents/{incident_id}/timeline",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        sources = {event["source"] for event in body["events"]}
        assert "incident" in sources
        assert "alert" in sources
        actions = [event["action"] for event in body["events"]]
        assert "incident_created" in actions
        assert "alert_linked" in actions
        assert "comment" in actions
        # Alert-side activities should carry alert_id reference
        alert_events = [event for event in body["events"] if event["source"] == "alert"]
        assert any(event["alert_id"] == str(alert_id) for event in alert_events)

    async def test_timeline_sorted_desc(self, client, registered_analyst):
        incident_id = await _create_incident(client, registered_analyst["headers"])
        alert_id = await _create_alert(client)
        await _link(client, registered_analyst["headers"], incident_id, alert_id)

        resp = await client.get(
            f"/api/v1/incidents/{incident_id}/timeline",
            headers=registered_analyst["headers"],
        )
        events = resp.json()["events"]
        assert len(events) >= 2
        timestamps = [event["created_at"] for event in events]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_timeline_only_includes_linked_alert_activities(self, client, registered_analyst):
        incident_id = await _create_incident(client, registered_analyst["headers"])
        linked_alert = await _create_alert(client, rule_name="Linked Alert")
        unrelated_alert = await _create_alert(client, rule_name="Unrelated Alert")
        await _link(client, registered_analyst["headers"], incident_id, linked_alert)

        # Comment on the unrelated alert should not leak into the timeline
        await client.post(
            f"/api/v1/alerts/{unrelated_alert}/comments",
            json={"text": "Unrelated"},
            headers=registered_analyst["headers"],
        )
        await client.post(
            f"/api/v1/alerts/{linked_alert}/comments",
            json={"text": "Linked"},
            headers=registered_analyst["headers"],
        )

        resp = await client.get(
            f"/api/v1/incidents/{incident_id}/timeline",
            headers=registered_analyst["headers"],
        )
        events = resp.json()["events"]
        details = [event.get("detail") for event in events]
        assert "Linked" in details
        assert "Unrelated" not in details


class TestIncidentTimelineFilters:
    async def test_filter_alert_only(self, client, registered_analyst):
        incident_id = await _create_incident(client, registered_analyst["headers"])
        alert_id = await _create_alert(client)
        await _link(client, registered_analyst["headers"], incident_id, alert_id)
        await client.post(
            f"/api/v1/alerts/{alert_id}/comments",
            json={"text": "Alert-only"},
            headers=registered_analyst["headers"],
        )

        resp = await client.get(
            f"/api/v1/incidents/{incident_id}/timeline?event_type=alert",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) >= 1
        assert all(event["source"] == "alert" for event in events)

    async def test_filter_incident_only(self, client, registered_analyst):
        incident_id = await _create_incident(client, registered_analyst["headers"])
        alert_id = await _create_alert(client)
        await _link(client, registered_analyst["headers"], incident_id, alert_id)

        resp = await client.get(
            f"/api/v1/incidents/{incident_id}/timeline?event_type=incident",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) >= 1
        assert all(event["source"] == "incident" for event in events)

    async def test_filter_comments_only(self, client, registered_analyst):
        incident_id = await _create_incident(client, registered_analyst["headers"])
        alert_id = await _create_alert(client)
        await _link(client, registered_analyst["headers"], incident_id, alert_id)

        await client.post(
            f"/api/v1/alerts/{alert_id}/comments",
            json={"text": "Alert comment"},
            headers=registered_analyst["headers"],
        )
        await client.post(
            f"/api/v1/incidents/{incident_id}/comments",
            json={"text": "Incident comment"},
            headers=registered_analyst["headers"],
        )

        resp = await client.get(
            f"/api/v1/incidents/{incident_id}/timeline?event_type=comment",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) == 2
        assert all(event["action"] == "comment" for event in events)


class TestIncidentTimelinePagination:
    async def test_pagination_limit_and_offset(self, client, registered_analyst):
        incident_id = await _create_incident(client, registered_analyst["headers"])

        for idx in range(5):
            await client.post(
                f"/api/v1/incidents/{incident_id}/comments",
                json={"text": f"Comment {idx}"},
                headers=registered_analyst["headers"],
            )

        resp = await client.get(
            f"/api/v1/incidents/{incident_id}/timeline?limit=2&offset=0",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 2
        assert data["total"] >= 6  # 5 comments + incident_created

        page_two = await client.get(
            f"/api/v1/incidents/{incident_id}/timeline?limit=2&offset=2",
            headers=registered_analyst["headers"],
        )
        assert page_two.status_code == 200
        page_two_data = page_two.json()
        assert len(page_two_data["events"]) == 2
        first_page_ids = {event["id"] for event in data["events"]}
        second_page_ids = {event["id"] for event in page_two_data["events"]}
        assert first_page_ids.isdisjoint(second_page_ids)

    async def test_pagination_limit_cap(self, client, registered_analyst):
        incident_id = await _create_incident(client, registered_analyst["headers"])
        resp = await client.get(
            f"/api/v1/incidents/{incident_id}/timeline?limit=500",
            headers=registered_analyst["headers"],
        )
        # Matches alert activities API which caps at 200
        assert resp.status_code == 422


class TestIncidentTimelineTenantScoping:
    async def test_tenant_validator_blocks_timeline(self, client, registered_analyst):
        from opensoar.main import app

        incident_id = await _create_incident(
            client, registered_analyst["headers"], title="Blocked Timeline Access"
        )

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is not None and getattr(resource, "title", "").startswith("Blocked"):
                raise HTTPException(status_code=403, detail="Tenant access denied")

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            resp = await client.get(
                f"/api/v1/incidents/{incident_id}/timeline",
                headers=registered_analyst["headers"],
            )
        finally:
            app.state.tenant_access_validators = original_validators

        assert resp.status_code == 403

    async def test_tenant_validator_scopes_linked_alert_activities(
        self, client, registered_analyst
    ):
        """Alert activities from alerts the validator blocks must not leak through."""
        from opensoar.main import app

        incident_id = await _create_incident(client, registered_analyst["headers"])
        allowed_alert = await _create_alert(client, rule_name="Allowed", partner="acme-corp")
        blocked_alert = await _create_alert(client, rule_name="Blocked", partner="globex")

        await _link(client, registered_analyst["headers"], incident_id, allowed_alert)
        await _link(client, registered_analyst["headers"], incident_id, blocked_alert)

        await client.post(
            f"/api/v1/alerts/{allowed_alert}/comments",
            json={"text": "Allowed comment"},
            headers=registered_analyst["headers"],
        )
        await client.post(
            f"/api/v1/alerts/{blocked_alert}/comments",
            json={"text": "Blocked comment"},
            headers=registered_analyst["headers"],
        )

        from opensoar.models.alert import Alert

        async def validator(**kwargs):
            query = kwargs.get("query")
            if query is not None and kwargs.get("resource_type") == "alert":
                return query.where(Alert.partner != "globex")
            return None

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            resp = await client.get(
                f"/api/v1/incidents/{incident_id}/timeline",
                headers=registered_analyst["headers"],
            )
        finally:
            app.state.tenant_access_validators = original_validators

        assert resp.status_code == 200
        events = resp.json()["events"]
        details = [event.get("detail") for event in events]
        assert "Allowed comment" in details
        assert "Blocked comment" not in details


class TestIncidentTimelineMentions:
    async def test_timeline_exposes_mentions_on_comment_events(
        self, client, registered_analyst
    ):
        mentioned = f"mention_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": mentioned,
                "display_name": mentioned.title(),
                "email": f"{mentioned}@opensoar.app",
                "password": "testpassword123",
            },
        )

        incident_id = await _create_incident(client, registered_analyst["headers"])
        await client.post(
            f"/api/v1/incidents/{incident_id}/comments",
            json={"text": f"hey @{mentioned} take a look"},
            headers=registered_analyst["headers"],
        )

        resp = await client.get(
            f"/api/v1/incidents/{incident_id}/timeline?event_type=comment",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) == 1
        assert events[0]["mentions"] == [mentioned.lower()]
