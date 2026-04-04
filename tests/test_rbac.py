"""Tests for RBAC — role-based access control with fine-grained permissions."""
from __future__ import annotations

import uuid

from opensoar.auth.rbac import Permission, has_permission


class TestRolePermissions:
    def test_admin_has_all_permissions(self):
        """Admin role should have all permissions."""
        for perm in Permission:
            assert has_permission("admin", perm), f"Admin missing {perm}"

    def test_analyst_can_read_alerts(self):
        assert has_permission("analyst", Permission.ALERTS_READ)

    def test_analyst_can_update_alerts(self):
        assert has_permission("analyst", Permission.ALERTS_UPDATE)

    def test_analyst_cannot_manage_analysts(self):
        assert not has_permission("analyst", Permission.ANALYSTS_MANAGE)

    def test_analyst_cannot_manage_api_keys(self):
        assert not has_permission("analyst", Permission.API_KEYS_MANAGE)

    def test_viewer_can_read(self):
        assert has_permission("viewer", Permission.ALERTS_READ)
        assert has_permission("viewer", Permission.INCIDENTS_READ)
        assert has_permission("viewer", Permission.PLAYBOOKS_READ)

    def test_viewer_cannot_write(self):
        assert not has_permission("viewer", Permission.ALERTS_UPDATE)
        assert not has_permission("viewer", Permission.INCIDENTS_CREATE)
        assert not has_permission("viewer", Permission.PLAYBOOKS_MANAGE)

    def test_tenant_admin_can_manage_playbooks_and_integrations(self):
        assert has_permission("tenant_admin", Permission.PLAYBOOKS_MANAGE)
        assert has_permission("tenant_admin", Permission.INTEGRATIONS_MANAGE)
        assert has_permission("tenant_admin", Permission.INCIDENTS_UPDATE)
        assert not has_permission("tenant_admin", Permission.ANALYSTS_MANAGE)

    def test_playbook_author_has_narrower_authoring_permissions(self):
        assert has_permission("playbook_author", Permission.PLAYBOOKS_READ)
        assert has_permission("playbook_author", Permission.PLAYBOOKS_MANAGE)
        assert has_permission("playbook_author", Permission.PLAYBOOKS_EXECUTE)
        assert has_permission("playbook_author", Permission.INTEGRATIONS_READ)
        assert not has_permission("playbook_author", Permission.INTEGRATIONS_MANAGE)
        assert not has_permission("playbook_author", Permission.INCIDENTS_UPDATE)

    def test_unknown_role_has_no_permissions(self):
        assert not has_permission("nonexistent", Permission.ALERTS_READ)


class TestRBACEndpoints:
    async def test_viewer_cannot_create_incident(self, client, db_session_factory):
        """A viewer should get 403 when trying to create an incident."""
        from opensoar.auth.jwt import create_access_token
        from opensoar.models.analyst import Analyst

        async with db_session_factory() as session:
            viewer = Analyst(
                username=f"viewer_{uuid.uuid4().hex[:8]}",
                display_name="Test Viewer",
                password_hash="$2b$12$LJ3m4ys3Lz0Y1r2VQz5Zu.dummyhashnotreal000000000000000",
                role="viewer",
            )
            session.add(viewer)
            await session.commit()
            token = create_access_token(viewer.id, viewer.username)

        resp = await client.post(
            "/api/v1/incidents",
            json={"title": "Viewer Test", "severity": "low"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_analyst_can_create_incident(self, client, registered_analyst):
        resp = await client.post(
            "/api/v1/incidents",
            json={"title": "Analyst Create Test", "severity": "low"},
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 201


class TestAuditLog:
    async def test_audit_log_records_actions(self, client, registered_analyst):
        """Actions should be recorded in the audit log."""
        # Create an alert via webhook
        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Audit Test", "severity": "high"},
        )
        alert_id = resp.json()["alert_id"]

        # Update it (should create audit entry)
        await client.patch(
            f"/api/v1/alerts/{alert_id}",
            json={"severity": "critical"},
            headers=registered_analyst["headers"],
        )

        # Check activities
        resp = await client.get(f"/api/v1/alerts/{alert_id}/activities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["activities"]) >= 1
