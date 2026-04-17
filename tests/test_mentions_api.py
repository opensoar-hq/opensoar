"""Integration tests for @mentions inside alert and incident comments."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from opensoar.notifications import clear_notification_hooks, register_notification_hook
from opensoar.plugins import register_tenant_access_validator


async def _register_analyst(client, username: str) -> dict:
    """Register a fresh analyst and return headers + payload."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "display_name": username.title(),
            "email": f"{username}@opensoar.app",
            "password": "testpassword123",
        },
    )
    data = resp.json()
    return {
        "token": data["access_token"],
        "analyst": data["analyst"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
    }


@pytest.fixture(autouse=True)
def _clear_notification_hooks():
    clear_notification_hooks()
    yield
    clear_notification_hooks()


class TestAlertCommentMentions:
    async def test_known_mention_is_stored(self, client, registered_analyst):
        mentioned = await _register_analyst(client, f"mentioned_{uuid.uuid4().hex[:6]}")

        alert_resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Mention Alert", "severity": "low"},
        )
        alert_id = alert_resp.json()["alert_id"]

        comment = await client.post(
            f"/api/v1/alerts/{alert_id}/comments",
            json={"text": f"@{mentioned['analyst']['username']} please review"},
            headers=registered_analyst["headers"],
        )
        assert comment.status_code == 200
        body = comment.json()
        assert body["mentions"] == [mentioned["analyst"]["username"].lower()]

    async def test_unknown_mentions_are_ignored(self, client, registered_analyst):
        alert_resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Unknown Mention Alert", "severity": "low"},
        )
        alert_id = alert_resp.json()["alert_id"]

        comment = await client.post(
            f"/api/v1/alerts/{alert_id}/comments",
            json={"text": "hi @nobody_here_yet please take a look"},
            headers=registered_analyst["headers"],
        )
        assert comment.status_code == 200
        body = comment.json()
        # Unknown usernames must not error the whole comment.
        assert body["detail"] == "hi @nobody_here_yet please take a look"
        assert body["mentions"] == []

    async def test_cross_tenant_mentions_are_rejected(self, client, registered_analyst):
        from opensoar.main import app

        # Register an analyst and tag them as belonging to a separate tenant via
        # a custom validator.  The tenant hook rejects read access for the
        # caller so the mentioned user looks invisible across tenants.
        other = await _register_analyst(client, f"other_{uuid.uuid4().hex[:6]}")

        alert_resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Cross Tenant Mention", "severity": "low"},
        )
        alert_id = alert_resp.json()["alert_id"]

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            resource_type = kwargs.get("resource_type")
            # Reject visibility of the "other" analyst only — everything else
            # passes through.
            if resource_type == "analyst" and resource is not None:
                if getattr(resource, "username", None) == other["analyst"]["username"]:
                    raise HTTPException(status_code=403, detail="cross tenant")

        original = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            comment = await client.post(
                f"/api/v1/alerts/{alert_id}/comments",
                json={"text": f"@{other['analyst']['username']} hi"},
                headers=registered_analyst["headers"],
            )
        finally:
            app.state.tenant_access_validators = original

        assert comment.status_code == 200
        # Cross-tenant mention treated like an unknown user — ignored, not an error.
        assert comment.json()["mentions"] == []

    async def test_notification_hook_fires_per_mention(self, client, registered_analyst):
        alice = await _register_analyst(client, f"alice_{uuid.uuid4().hex[:6]}")
        bob = await _register_analyst(client, f"bob_{uuid.uuid4().hex[:6]}")

        captured: list[str] = []

        async def hook(notification):
            captured.append(notification.recipient_username)

        register_notification_hook(hook)

        alert_resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Notify Alert", "severity": "low"},
        )
        alert_id = alert_resp.json()["alert_id"]

        await client.post(
            f"/api/v1/alerts/{alert_id}/comments",
            json={
                "text": (
                    f"@{alice['analyst']['username']} and "
                    f"@{bob['analyst']['username']} please triage"
                )
            },
            headers=registered_analyst["headers"],
        )

        assert sorted(captured) == sorted(
            [
                alice["analyst"]["username"].lower(),
                bob["analyst"]["username"].lower(),
            ]
        )

    async def test_edit_recomputes_mentions(self, client, registered_analyst):
        mentioned = await _register_analyst(client, f"edit_{uuid.uuid4().hex[:6]}")

        alert_resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Edit Mention Alert", "severity": "low"},
        )
        alert_id = alert_resp.json()["alert_id"]

        comment = await client.post(
            f"/api/v1/alerts/{alert_id}/comments",
            json={"text": "no mention yet"},
            headers=registered_analyst["headers"],
        )
        comment_id = comment.json()["id"]
        assert comment.json()["mentions"] == []

        edited = await client.patch(
            f"/api/v1/alerts/{alert_id}/comments/{comment_id}",
            json={"text": f"now @{mentioned['analyst']['username']}"},
            headers=registered_analyst["headers"],
        )
        assert edited.status_code == 200
        assert edited.json()["mentions"] == [mentioned["analyst"]["username"].lower()]


class TestIncidentCommentMentions:
    async def test_known_mention_is_stored(self, client, registered_analyst):
        mentioned = await _register_analyst(client, f"incmention_{uuid.uuid4().hex[:6]}")

        incident = await client.post(
            "/api/v1/incidents",
            json={"title": "Mention Incident", "severity": "low"},
            headers=registered_analyst["headers"],
        )
        incident_id = incident.json()["id"]

        comment = await client.post(
            f"/api/v1/incidents/{incident_id}/comments",
            json={"text": f"@{mentioned['analyst']['username']} FYI"},
            headers=registered_analyst["headers"],
        )
        assert comment.status_code == 200
        assert comment.json()["mentions"] == [mentioned["analyst"]["username"].lower()]

    async def test_notification_hook_fires_per_mention(self, client, registered_analyst):
        alice = await _register_analyst(client, f"iali_{uuid.uuid4().hex[:6]}")

        captured: list[str] = []

        def hook(notification):
            captured.append(notification.recipient_username)

        register_notification_hook(hook)

        incident = await client.post(
            "/api/v1/incidents",
            json={"title": "Notify Incident", "severity": "low"},
            headers=registered_analyst["headers"],
        )
        incident_id = incident.json()["id"]

        await client.post(
            f"/api/v1/incidents/{incident_id}/comments",
            json={"text": f"@{alice['analyst']['username']} help please"},
            headers=registered_analyst["headers"],
        )
        assert captured == [alice["analyst"]["username"].lower()]


class TestMentionSuggestEndpoint:
    async def test_lists_mentionable_analysts(self, client, registered_analyst):
        other = await _register_analyst(client, f"sugg_{uuid.uuid4().hex[:6]}")

        resp = await client.get(
            f"/api/v1/auth/analysts/mentionable?q={other['analyst']['username'][:4]}",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        usernames = [a["username"] for a in resp.json()]
        assert other["analyst"]["username"] in usernames

    async def test_filters_by_prefix(self, client, registered_analyst):
        target = await _register_analyst(client, f"filterme_{uuid.uuid4().hex[:6]}")

        resp = await client.get(
            "/api/v1/auth/analysts/mentionable?q=filterme",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        usernames = [a["username"] for a in resp.json()]
        assert target["analyst"]["username"] in usernames
        assert all(u.lower().startswith("filterme") for u in usernames)

    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/auth/analysts/mentionable")
        assert resp.status_code in (401, 403)
