"""Tests for incident templates and template-driven incident creation."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from opensoar.plugins import register_tenant_access_validator


async def _create_template(client, headers, **overrides) -> dict:
    body = {
        "name": f"tmpl-{uuid.uuid4().hex[:8]}",
        "description": "Template for phishing incidents",
        "default_severity": "high",
        "default_tags": ["phishing", "email"],
        "playbook_ids": [],
        "observable_types": ["email", "url", "domain"],
    }
    body.update(overrides)
    resp = await client.post(
        "/api/v1/incident-templates",
        json=body,
        headers=headers,
    )
    return resp


class TestIncidentTemplateCRUD:
    async def test_create_template(self, client, registered_admin):
        resp = await _create_template(
            client,
            registered_admin["headers"],
            name="Phishing Response",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Phishing Response"
        assert data["default_severity"] == "high"
        assert data["default_tags"] == ["phishing", "email"]
        assert data["observable_types"] == ["email", "url", "domain"]
        assert data["playbook_ids"] == []
        assert "id" in data and "created_at" in data

    async def test_create_template_requires_admin(self, client, registered_analyst):
        resp = await _create_template(client, registered_analyst["headers"])
        # analyst role lacks SETTINGS_MANAGE permission
        assert resp.status_code == 403

    async def test_create_template_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/incident-templates",
            json={"name": "unauth", "default_severity": "low"},
        )
        assert resp.status_code == 401

    async def test_list_templates(self, client, registered_admin):
        await _create_template(client, registered_admin["headers"], name="A Template")
        await _create_template(client, registered_admin["headers"], name="B Template")
        resp = await client.get(
            "/api/v1/incident-templates",
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        names = {t["name"] for t in data["templates"]}
        assert {"A Template", "B Template"}.issubset(names)

    async def test_get_template(self, client, registered_admin):
        create = await _create_template(
            client, registered_admin["headers"], name="Get Target"
        )
        template_id = create.json()["id"]
        resp = await client.get(
            f"/api/v1/incident-templates/{template_id}",
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Target"

    async def test_get_nonexistent_template(self, client, registered_admin):
        resp = await client.get(
            f"/api/v1/incident-templates/{uuid.uuid4()}",
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 404

    async def test_update_template(self, client, registered_admin):
        create = await _create_template(
            client, registered_admin["headers"], name="Edit Me"
        )
        template_id = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/incident-templates/{template_id}",
            json={
                "description": "Updated desc",
                "default_severity": "critical",
                "default_tags": ["phishing", "credential-harvest"],
            },
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated desc"
        assert data["default_severity"] == "critical"
        assert data["default_tags"] == ["phishing", "credential-harvest"]

    async def test_delete_template(self, client, registered_admin):
        create = await _create_template(
            client, registered_admin["headers"], name="To Delete"
        )
        template_id = create.json()["id"]
        resp = await client.delete(
            f"/api/v1/incident-templates/{template_id}",
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 200

        resp = await client.get(
            f"/api/v1/incident-templates/{template_id}",
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 404


class TestIncidentTemplateTenantScoping:
    async def test_tenant_validator_filters_list(self, client, registered_admin):
        from opensoar.main import app
        from opensoar.models.incident_template import IncidentTemplate

        await _create_template(
            client, registered_admin["headers"], name="Scoped Template"
        )
        await _create_template(
            client, registered_admin["headers"], name="Blocked Template"
        )

        async def validator(**kwargs):
            query = kwargs.get("query")
            if query is not None and kwargs["resource_type"] == "incident_template":
                return query.where(IncidentTemplate.name == "Scoped Template")
            return None

        original = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            resp = await client.get(
                "/api/v1/incident-templates",
                headers=registered_admin["headers"],
            )
        finally:
            app.state.tenant_access_validators = original

        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()["templates"]}
        assert names == {"Scoped Template"}

    async def test_tenant_validator_blocks_detail_and_update(
        self, client, registered_admin
    ):
        from opensoar.main import app

        create = await _create_template(
            client, registered_admin["headers"], name="Blocked Detail Tmpl"
        )
        template_id = create.json()["id"]

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is not None and getattr(resource, "name", "").startswith(
                "Blocked"
            ):
                raise HTTPException(status_code=403, detail="Tenant access denied")

        original = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            detail = await client.get(
                f"/api/v1/incident-templates/{template_id}",
                headers=registered_admin["headers"],
            )
            update = await client.patch(
                f"/api/v1/incident-templates/{template_id}",
                json={"default_severity": "critical"},
                headers=registered_admin["headers"],
            )
            delete = await client.delete(
                f"/api/v1/incident-templates/{template_id}",
                headers=registered_admin["headers"],
            )
        finally:
            app.state.tenant_access_validators = original

        assert detail.status_code == 403
        assert update.status_code == 403
        assert delete.status_code == 403


class TestCreateIncidentFromTemplate:
    async def test_create_incident_applies_template_defaults(
        self, client, registered_admin, registered_analyst
    ):
        create = await _create_template(
            client,
            registered_admin["headers"],
            name="Phishing Defaults",
            default_severity="critical",
            default_tags=["phishing", "email"],
        )
        template_id = create.json()["id"]

        resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Phish on finance team",
                "template_id": template_id,
            },
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "critical"
        assert set(data["tags"] or []) == {"phishing", "email"}

    async def test_explicit_fields_override_template_defaults(
        self, client, registered_admin, registered_analyst
    ):
        create = await _create_template(
            client,
            registered_admin["headers"],
            name="Override Defaults",
            default_severity="low",
            default_tags=["phishing"],
        )
        template_id = create.json()["id"]

        resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Override me",
                "template_id": template_id,
                "severity": "high",
                "tags": ["custom"],
            },
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "high"
        assert data["tags"] == ["custom"]

    async def test_template_not_found_returns_400(
        self, client, registered_analyst
    ):
        resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Bad template",
                "template_id": str(uuid.uuid4()),
            },
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 400

    async def test_template_auto_runs_listed_playbooks(
        self, client, registered_admin, registered_analyst, session
    ):
        """When creating from a template with playbook_ids, those playbooks run."""
        from opensoar.models.playbook import PlaybookDefinition

        pb = PlaybookDefinition(
            name=f"pb_{uuid.uuid4().hex[:8]}",
            module_path="playbooks.examples.noop",
            function_name="noop",
            enabled=True,
        )
        session.add(pb)
        await session.commit()
        await session.refresh(pb)

        create = await _create_template(
            client,
            registered_admin["headers"],
            name="Runs Playbooks",
            playbook_ids=[str(pb.id)],
        )
        template_id = create.json()["id"]

        delayed = []

        def fake_delay(playbook_name, alert_id=None):
            delayed.append((playbook_name, alert_id))
            task = MagicMock()
            task.id = "task-123"
            return task

        with patch(
            "opensoar.worker.tasks.execute_playbook_task.delay",
            side_effect=fake_delay,
        ):
            resp = await client.post(
                "/api/v1/incidents",
                json={
                    "title": "Template run",
                    "template_id": template_id,
                },
                headers=registered_analyst["headers"],
            )
        assert resp.status_code == 201
        assert [name for name, _ in delayed] == [pb.name]


class TestIncidentTemplateSeed:
    async def test_seed_templates_loadable(self):
        from opensoar.seed_templates import SEED_INCIDENT_TEMPLATES

        names = {t["name"] for t in SEED_INCIDENT_TEMPLATES}
        assert {"Phishing", "Ransomware", "Data Exfiltration"}.issubset(names)
        for tmpl in SEED_INCIDENT_TEMPLATES:
            assert tmpl["default_severity"] in {"low", "medium", "high", "critical"}
            assert isinstance(tmpl["default_tags"], list)
            assert isinstance(tmpl["observable_types"], list)
