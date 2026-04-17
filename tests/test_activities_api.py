from __future__ import annotations

from fastapi import HTTPException

from opensoar.plugins import register_tenant_access_validator


class TestActivityTenantHooks:
    async def test_tenant_validator_blocks_alert_activities(self, client, registered_analyst):
        from opensoar.main import app

        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Blocked Activities", "severity": "low", "partner": "globex"},
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
            blocked = await client.get(
                f"/api/v1/alerts/{alert_id}/activities",
                headers=registered_analyst["headers"],
            )
        finally:
            app.state.tenant_access_validators = original_validators

        assert blocked.status_code == 403

    async def test_tenant_validator_blocks_alert_comment_create(self, client, registered_analyst):
        from opensoar.main import app

        created = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Blocked Comment Create", "severity": "low", "partner": "globex"},
        )
        alert_id = created.json()["alert_id"]

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is not None and getattr(resource, "partner", None) == "globex":
                raise HTTPException(status_code=403, detail="Tenant access denied")

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            blocked = await client.post(
                f"/api/v1/alerts/{alert_id}/comments",
                json={"text": "This should be blocked"},
                headers=registered_analyst["headers"],
            )
        finally:
            app.state.tenant_access_validators = original_validators

        assert blocked.status_code == 403

    async def test_tenant_validator_blocks_alert_comment_edit(self, client, registered_analyst):
        from opensoar.main import app

        created = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Blocked Comment Edit", "severity": "low", "partner": "globex"},
        )
        alert_id = created.json()["alert_id"]

        comment = await client.post(
            f"/api/v1/alerts/{alert_id}/comments",
            json={"text": "Original comment"},
            headers=registered_analyst["headers"],
        )
        comment_id = comment.json()["id"]

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is not None and getattr(resource, "partner", None) == "globex":
                raise HTTPException(status_code=403, detail="Tenant access denied")

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            blocked = await client.patch(
                f"/api/v1/alerts/{alert_id}/comments/{comment_id}",
                json={"text": "Edited should be blocked"},
                headers=registered_analyst["headers"],
            )
        finally:
            app.state.tenant_access_validators = original_validators

        assert blocked.status_code == 403
