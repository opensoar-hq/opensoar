"""Tests for data retention policy enforcement (Issue #86)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from opensoar.auth.rbac import Permission, has_permission
from opensoar.config import settings
from opensoar.models.activity import Activity
from opensoar.models.alert import Alert
from opensoar.models.incident import Incident


def _past(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


class TestRetentionSettings:
    def test_default_retention_values(self):
        assert settings.alerts_retention_days == 365
        assert settings.incidents_retention_days == 730
        assert settings.activities_retention_days == 365
        assert settings.retention_grace_days == 30


class TestRetentionPermission:
    def test_admin_has_retention_manage(self):
        assert has_permission("admin", Permission.RETENTION_MANAGE)

    def test_analyst_cannot_manage_retention(self):
        assert not has_permission("analyst", Permission.RETENTION_MANAGE)

    def test_viewer_cannot_manage_retention(self):
        assert not has_permission("viewer", Permission.RETENTION_MANAGE)


class TestRetentionService:
    async def test_dry_run_returns_counts_no_mutation(self, session):
        from opensoar.retention.service import run_retention_purge

        old_alert = Alert(
            source="webhook",
            source_id=f"old-{uuid.uuid4().hex[:8]}",
            title="Old resolved alert",
            severity="low",
            status="resolved",
            resolved_at=_past(400),
        )
        recent_alert = Alert(
            source="webhook",
            source_id=f"recent-{uuid.uuid4().hex[:8]}",
            title="Recent resolved alert",
            severity="low",
            status="resolved",
            resolved_at=_past(10),
        )
        session.add_all([old_alert, recent_alert])
        await session.commit()

        result = await run_retention_purge(session, dry_run=True)

        assert result["dry_run"] is True
        assert result["alerts"]["soft_delete_candidates"] >= 1
        # Nothing changed
        await session.refresh(old_alert)
        assert old_alert.archived_at is None

    async def test_purge_soft_deletes_old_resolved_alerts(self, session):
        from opensoar.retention.service import run_retention_purge

        alert = Alert(
            source="webhook",
            source_id=f"old-{uuid.uuid4().hex[:8]}",
            title="Stale resolved alert",
            severity="low",
            status="resolved",
            resolved_at=_past(400),
        )
        session.add(alert)
        await session.commit()

        result = await run_retention_purge(session, dry_run=False)

        assert result["dry_run"] is False
        assert result["alerts"]["soft_deleted"] >= 1
        await session.refresh(alert)
        assert alert.archived_at is not None

    async def test_purge_hard_deletes_after_grace(self, session):
        from opensoar.retention.service import run_retention_purge

        archived_past_grace = _past(settings.retention_grace_days + 5)
        alert = Alert(
            source="webhook",
            source_id=f"purge-{uuid.uuid4().hex[:8]}",
            title="Long-archived alert",
            severity="low",
            status="resolved",
            resolved_at=_past(500),
            archived_at=archived_past_grace,
        )
        session.add(alert)
        await session.commit()
        alert_id = alert.id

        result = await run_retention_purge(session, dry_run=False)

        assert result["alerts"]["hard_deleted"] >= 1
        remaining = (
            await session.execute(select(Alert).where(Alert.id == alert_id))
        ).scalar_one_or_none()
        assert remaining is None

    async def test_grace_period_respected(self, session):
        """Alerts archived within the grace period must NOT be hard-deleted."""
        from opensoar.retention.service import run_retention_purge

        recently_archived = _past(5)  # well within 30-day grace
        alert = Alert(
            source="webhook",
            source_id=f"grace-{uuid.uuid4().hex[:8]}",
            title="Archived in grace window",
            severity="low",
            status="resolved",
            resolved_at=_past(500),
            archived_at=recently_archived,
        )
        session.add(alert)
        await session.commit()
        alert_id = alert.id

        await run_retention_purge(session, dry_run=False)

        survivor = (
            await session.execute(select(Alert).where(Alert.id == alert_id))
        ).scalar_one_or_none()
        assert survivor is not None
        assert survivor.archived_at is not None

    async def test_purge_does_not_touch_open_incidents(self, session):
        from opensoar.retention.service import run_retention_purge

        open_incident = Incident(
            title="Open incident",
            severity="medium",
            status="open",
        )
        session.add(open_incident)
        await session.commit()
        incident_id = open_incident.id

        await run_retention_purge(session, dry_run=False)

        surviving = (
            await session.execute(select(Incident).where(Incident.id == incident_id))
        ).scalar_one_or_none()
        assert surviving is not None
        assert surviving.archived_at is None

    async def test_purge_writes_audit_activity(self, session):
        from opensoar.retention.service import run_retention_purge

        alert = Alert(
            source="webhook",
            source_id=f"audit-{uuid.uuid4().hex[:8]}",
            title="Audit-test alert",
            severity="low",
            status="resolved",
            resolved_at=_past(500),
        )
        session.add(alert)
        await session.commit()

        await run_retention_purge(session, dry_run=False)

        rows = (
            await session.execute(
                select(Activity).where(Activity.action == "retention_purge")
            )
        ).scalars().all()
        assert len(rows) >= 1
        entry = rows[-1]
        assert entry.metadata_json is not None
        assert "alerts" in entry.metadata_json


class TestRetentionEndpoint:
    async def test_non_admin_cannot_call_endpoint(self, client, registered_analyst):
        resp = await client.post(
            "/api/v1/admin/retention/purge?dry_run=true",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 403

    async def test_unauthenticated_rejected(self, client):
        resp = await client.post("/api/v1/admin/retention/purge?dry_run=true")
        assert resp.status_code in {401, 403}

    async def test_admin_dry_run_returns_counts(self, client, registered_admin):
        resp = await client.post(
            "/api/v1/admin/retention/purge?dry_run=true",
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is True
        assert "alerts" in data
        assert "incidents" in data
        assert "activities" in data

    async def test_admin_real_purge_succeeds(self, client, registered_admin):
        resp = await client.post(
            "/api/v1/admin/retention/purge?dry_run=false",
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is False


@pytest.mark.asyncio
async def test_celery_beat_task_registered():
    from opensoar.worker.retention import purge_retention_task

    assert purge_retention_task is not None
    assert purge_retention_task.name == "opensoar.purge_retention"
