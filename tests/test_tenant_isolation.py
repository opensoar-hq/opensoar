"""Cross-tenant isolation test suite (issue #113).

Validates that every multi-tenant-scoped query path runs through the
``apply_tenant_access_query``/``enforce_tenant_access`` plugin hook so optional
packages can scope results and block cross-tenant reads or writes. The core
package has no built-in tenant definition — these tests register a custom
validator that keys off the ``partner`` field on alerts (and inferred tenant
membership on ancestor-linked records like runs/observables/activities) to
prove the hook fires everywhere it must.

Two analysts in different "tenants" (partners acme-corp and globex) each own
alerts + downstream records. Analyst A must never be able to read or mutate
analyst B's records through any endpoint.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException

from opensoar.plugins import register_tenant_access_validator


# ── Shared test helpers ────────────────────────────────────────


class _SwapValidators:
    """Replace registered validators for the duration of a ``with`` block."""

    def __init__(self, app, validators):
        self.app = app
        self.validators = validators
        self.previous: list = []

    def __enter__(self):
        self.previous = list(self.app.state.tenant_access_validators)
        self.app.state.tenant_access_validators = []
        for validator in self.validators:
            register_tenant_access_validator(self.app, validator)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.app.state.tenant_access_validators = self.previous


def _swap_validators(app, *validators):
    return _SwapValidators(app, validators)


def _make_partner_validator(allowed_partner: str):
    """Return a validator that limits callers to ``allowed_partner``.

    The validator:
      * filters list queries by ``Alert.partner == allowed_partner`` when the
        query is over ``Alert``
      * filters ancestor-joined queries (runs, observables, activities) by
        walking back to the parent alert's partner
      * raises 403 on resource access for any non-matching record
    """

    async def validator(**kwargs):
        from sqlalchemy import select

        from opensoar.models.activity import Activity
        from opensoar.models.alert import Alert
        from opensoar.models.incident import Incident
        from opensoar.models.incident_alert import IncidentAlert
        from opensoar.models.observable import Observable
        from opensoar.models.playbook_run import PlaybookRun

        query = kwargs.get("query")
        if query is not None:
            rtype = kwargs.get("resource_type")
            if rtype in {"alert", "anomaly"}:
                # Both use a ``partner`` column directly.
                target = Alert if rtype == "alert" else query.froms_expected  # noqa: F841
                if rtype == "alert":
                    return query.where(Alert.partner == allowed_partner)
                # anomaly lives in its own model with a partner column
                from opensoar.models.anomaly import Anomaly

                return query.where(Anomaly.partner == allowed_partner)
            if rtype == "playbook_run":
                allowed_alert_ids = select(Alert.id).where(
                    Alert.partner == allowed_partner
                )
                return query.where(
                    PlaybookRun.alert_id.in_(allowed_alert_ids)
                )
            if rtype == "observable":
                allowed_alert_ids = select(Alert.id).where(
                    Alert.partner == allowed_partner
                )
                allowed_incident_ids = (
                    select(IncidentAlert.incident_id)
                    .join(Alert, Alert.id == IncidentAlert.alert_id)
                    .where(Alert.partner == allowed_partner)
                )
                return query.where(
                    (Observable.alert_id.in_(allowed_alert_ids))
                    | (Observable.incident_id.in_(allowed_incident_ids))
                )
            if rtype == "incident":
                allowed_incident_ids = (
                    select(IncidentAlert.incident_id)
                    .join(Alert, Alert.id == IncidentAlert.alert_id)
                    .where(Alert.partner == allowed_partner)
                )
                return query.where(Incident.id.in_(allowed_incident_ids))
            if rtype == "activity":
                allowed_alert_ids = select(Alert.id).where(
                    Alert.partner == allowed_partner
                )
                return query.where(
                    Activity.alert_id.in_(allowed_alert_ids)
                )
            return None

        # Resource enforcement path
        resource = kwargs.get("resource")
        if resource is None:
            return None

        partner = getattr(resource, "partner", None)
        if partner is not None:
            if partner != allowed_partner:
                raise HTTPException(status_code=403, detail="Tenant access denied")
            return

        alert_id = getattr(resource, "alert_id", None)
        if alert_id is not None:
            session = kwargs.get("session")
            parent_partner = (
                await session.execute(
                    select(Alert.partner).where(Alert.id == alert_id)
                )
            ).scalar_one_or_none()
            if parent_partner and parent_partner != allowed_partner:
                raise HTTPException(status_code=403, detail="Tenant access denied")
            return

        incident_id = getattr(resource, "incident_id", None)
        if incident_id is not None and isinstance(resource, Observable):
            session = kwargs.get("session")
            owner = (
                await session.execute(
                    select(Alert.partner)
                    .join(IncidentAlert, IncidentAlert.alert_id == Alert.id)
                    .where(IncidentAlert.incident_id == incident_id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if owner and owner != allowed_partner:
                raise HTTPException(status_code=403, detail="Tenant access denied")
            return

        # Incidents linking back through IncidentAlert
        if isinstance(resource, Incident):
            session = kwargs.get("session")
            owner = (
                await session.execute(
                    select(Alert.partner)
                    .join(IncidentAlert, IncidentAlert.alert_id == Alert.id)
                    .where(IncidentAlert.incident_id == resource.id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if owner and owner != allowed_partner:
                raise HTTPException(status_code=403, detail="Tenant access denied")

    return validator


async def _create_alert_with_partner(client, partner: str, title: str) -> str:
    resp = await client.post(
        "/api/v1/webhooks/alerts",
        json={
            "rule_name": title,
            "severity": "high",
            "source_ip": "10.0.0.1",
            "partner": partner,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["alert_id"]


# ── Tests ──────────────────────────────────────────────────────


class TestAlertTenantIsolation:
    async def test_list_alerts_filters_by_tenant(
        self, client, registered_analyst
    ):
        from opensoar.main import app

        await _create_alert_with_partner(client, "acme-corp", "A1")
        await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.get(
                "/api/v1/alerts", headers=registered_analyst["headers"]
            )

        assert resp.status_code == 200
        partners = {a["partner"] for a in resp.json()["alerts"]}
        assert "globex" not in partners
        assert partners <= {"acme-corp"}

    async def test_get_alert_detail_blocked_cross_tenant(
        self, client, registered_analyst
    ):
        from opensoar.main import app

        foreign_id = await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.get(
                f"/api/v1/alerts/{foreign_id}",
                headers=registered_analyst["headers"],
            )

        assert resp.status_code == 403

    async def test_patch_alert_blocked_cross_tenant(
        self, client, registered_analyst
    ):
        from opensoar.main import app

        foreign_id = await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.patch(
                f"/api/v1/alerts/{foreign_id}",
                headers=registered_analyst["headers"],
                json={"status": "in_progress"},
            )

        assert resp.status_code == 403

    async def test_claim_alert_blocked_cross_tenant(
        self, client, registered_analyst
    ):
        from opensoar.main import app

        foreign_id = await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.post(
                f"/api/v1/alerts/{foreign_id}/claim",
                headers=registered_analyst["headers"],
            )

        assert resp.status_code == 403

    async def test_delete_alert_blocked_cross_tenant(
        self, client, registered_admin
    ):
        from opensoar.main import app

        foreign_id = await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.delete(
                f"/api/v1/alerts/{foreign_id}",
                headers=registered_admin["headers"],
            )

        assert resp.status_code == 403

    async def test_bulk_update_isolates_foreign_alerts(
        self, client, registered_analyst
    ):
        """Bulk resolve must skip/deny alerts belonging to another tenant."""
        from opensoar.main import app

        mine = await _create_alert_with_partner(client, "acme-corp", "A1")
        foreign = await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.post(
                "/api/v1/alerts/bulk",
                headers=registered_analyst["headers"],
                json={
                    "alert_ids": [mine, foreign],
                    "action": "resolve",
                    "determination": "benign",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        # foreign must not be counted as updated — either failed or filtered out
        assert body["updated"] <= 1
        # foreign should be reported as unreachable / not found / denied
        assert body["failed"] >= 1 or body["updated"] == 1


class TestAlertRunsTenantIsolation:
    async def test_list_alert_runs_blocked_cross_tenant(
        self, client, registered_analyst
    ):
        from opensoar.main import app

        foreign_id = await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.get(
                f"/api/v1/alerts/{foreign_id}/runs",
                headers=registered_analyst["headers"],
            )

        # Either 403 from parent-alert check or filtered list — but never leaks
        assert resp.status_code in (403, 200)
        if resp.status_code == 200:
            # If scoped, runs list must be empty for cross-tenant alert
            assert resp.json()["total"] == 0

    async def test_global_runs_list_filtered_by_tenant(
        self, client, db_session_factory, registered_analyst
    ):
        from opensoar.main import app
        from opensoar.models.playbook import PlaybookDefinition
        from opensoar.models.playbook_run import PlaybookRun

        mine = uuid.UUID(
            await _create_alert_with_partner(client, "acme-corp", "A1")
        )
        foreign = uuid.UUID(
            await _create_alert_with_partner(client, "globex", "B1")
        )

        async with db_session_factory() as sess:
            pb = PlaybookDefinition(
                name=f"runs_test_{uuid.uuid4().hex[:6]}",
                module_path="test",
                function_name="fn",
                trigger_type="webhook",
                trigger_config={},
                enabled=True,
            )
            sess.add(pb)
            await sess.flush()
            sess.add_all(
                [
                    PlaybookRun(
                        playbook_id=pb.id,
                        alert_id=mine,
                        status="completed",
                    ),
                    PlaybookRun(
                        playbook_id=pb.id,
                        alert_id=foreign,
                        status="completed",
                    ),
                ]
            )
            await sess.commit()

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.get(
                "/api/v1/runs", headers=registered_analyst["headers"]
            )

        assert resp.status_code == 200
        returned_ids = {
            r["alert_id"] for r in resp.json()["runs"] if r.get("alert_id")
        }
        assert str(foreign) not in returned_ids


class TestObservableTenantIsolation:
    async def test_list_observables_scoped_to_tenant(
        self, client, db_session_factory, registered_analyst
    ):
        from opensoar.main import app
        from opensoar.models.observable import Observable

        mine = uuid.UUID(
            await _create_alert_with_partner(client, "acme-corp", "A1")
        )
        foreign = uuid.UUID(
            await _create_alert_with_partner(client, "globex", "B1")
        )

        async with db_session_factory() as sess:
            sess.add_all(
                [
                    Observable(
                        type="ip",
                        value=f"1.2.3.{uuid.uuid4().int % 254}",
                        source="test",
                        alert_id=mine,
                    ),
                    Observable(
                        type="ip",
                        value=f"4.5.6.{uuid.uuid4().int % 254}",
                        source="test",
                        alert_id=foreign,
                    ),
                ]
            )
            await sess.commit()

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.get(
                "/api/v1/observables", headers=registered_analyst["headers"]
            )

        assert resp.status_code == 200
        returned_alert_ids = {
            o["alert_id"]
            for o in resp.json()["observables"]
            if o.get("alert_id")
        }
        assert str(foreign) not in returned_alert_ids


class TestAiEndpointTenantIsolation:
    """AI endpoints must enforce tenant access before handing data to LLMs."""

    async def test_summarize_blocks_cross_tenant_alert(
        self, client, registered_analyst, monkeypatch
    ):
        from opensoar.main import app
        from opensoar.api import ai as ai_module

        # Stub the LLM client so we don't hit the network — the call should
        # never happen anyway because tenant enforcement should kick in first.
        class _FakeClient:
            async def complete(self, *a, **kw):  # pragma: no cover
                raise AssertionError(
                    "LLM must not be called when tenant access is denied"
                )

        monkeypatch.setattr(ai_module, "get_llm_client", lambda: _FakeClient())

        foreign_id = await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.post(
                "/api/v1/ai/summarize",
                headers=registered_analyst["headers"],
                json={"alert_id": foreign_id},
            )

        assert resp.status_code == 403

    async def test_triage_blocks_cross_tenant_alert(
        self, client, registered_analyst, monkeypatch
    ):
        from opensoar.main import app
        from opensoar.api import ai as ai_module

        class _FakeClient:
            async def complete(self, *a, **kw):  # pragma: no cover
                raise AssertionError(
                    "LLM must not be called when tenant access is denied"
                )

        monkeypatch.setattr(ai_module, "get_llm_client", lambda: _FakeClient())

        foreign_id = await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.post(
                "/api/v1/ai/triage",
                headers=registered_analyst["headers"],
                json={"alert_id": foreign_id},
            )

        assert resp.status_code == 403

    async def test_recommend_blocks_cross_tenant_alert(
        self, client, registered_analyst, monkeypatch
    ):
        from opensoar.main import app
        from opensoar.api import ai as ai_module

        class _FakeClient:
            async def complete(self, *a, **kw):  # pragma: no cover
                raise AssertionError(
                    "LLM must not be called when tenant access is denied"
                )

        monkeypatch.setattr(ai_module, "get_llm_client", lambda: _FakeClient())

        foreign_id = await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.post(
                "/api/v1/ai/recommend",
                headers=registered_analyst["headers"],
                json={"alert_id": foreign_id},
            )

        assert resp.status_code == 403

    async def test_deduplicate_blocks_cross_tenant_alert(
        self, client, registered_analyst, monkeypatch
    ):
        from opensoar.main import app
        from opensoar.api import ai_dedup as dedup_module

        class _FakeClient:
            provider = "openai"
            model = "fake"

            async def embed(self, *a, **kw):  # pragma: no cover
                raise AssertionError(
                    "Embedding must not be called when tenant access is denied"
                )

        monkeypatch.setattr(
            dedup_module, "get_embedding_client", lambda: _FakeClient()
        )

        foreign_id = await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.post(
                "/api/v1/ai/deduplicate",
                headers=registered_analyst["headers"],
                json={"alert_id": foreign_id},
            )

        assert resp.status_code == 403


class TestActivitiesTenantIsolation:
    async def test_list_alert_activities_blocked_cross_tenant(
        self, client, registered_analyst
    ):
        from opensoar.main import app

        foreign_id = await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.get(
                f"/api/v1/alerts/{foreign_id}/activities",
                headers=registered_analyst["headers"],
            )

        assert resp.status_code == 403

    async def test_add_comment_blocked_cross_tenant(
        self, client, registered_analyst
    ):
        from opensoar.main import app

        foreign_id = await _create_alert_with_partner(client, "globex", "B1")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.post(
                f"/api/v1/alerts/{foreign_id}/comments",
                headers=registered_analyst["headers"],
                json={"text": "hello"},
            )

        assert resp.status_code == 403


class TestDashboardTenantIsolation:
    async def test_dashboard_stats_filters_by_tenant(
        self, client, registered_analyst
    ):
        from opensoar.main import app

        await _create_alert_with_partner(client, "acme-corp", "A1")
        await _create_alert_with_partner(client, "globex", "B1")
        await _create_alert_with_partner(client, "globex", "B2")

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.get(
                "/api/v1/dashboard/stats",
                headers=registered_analyst["headers"],
            )

        assert resp.status_code == 200
        by_partner = resp.json()["alerts_by_partner"]
        assert "globex" not in by_partner
        # acme-corp's scoped total matches what was filtered in
        assert resp.json()["total_alerts"] == by_partner.get("acme-corp", 0)


class TestIncidentTenantIsolation:
    async def test_list_incident_activities_filtered_by_tenant(
        self, client, db_session_factory, registered_analyst
    ):
        """Activities linked to foreign alerts must not leak via the
        incident-activities endpoint."""
        from opensoar.main import app
        from opensoar.models.activity import Activity
        from opensoar.models.incident import Incident
        from opensoar.models.incident_alert import IncidentAlert

        mine = uuid.UUID(
            await _create_alert_with_partner(client, "acme-corp", "A1")
        )
        foreign = uuid.UUID(
            await _create_alert_with_partner(client, "globex", "B1")
        )

        async with db_session_factory() as sess:
            incident = Incident(title="shared", severity="medium")
            sess.add(incident)
            await sess.flush()
            sess.add_all(
                [
                    IncidentAlert(incident_id=incident.id, alert_id=mine),
                    IncidentAlert(incident_id=incident.id, alert_id=foreign),
                    Activity(
                        incident_id=incident.id,
                        alert_id=mine,
                        action="status_change",
                        detail="mine-only",
                    ),
                    Activity(
                        incident_id=incident.id,
                        alert_id=foreign,
                        action="status_change",
                        detail="foreign-only",
                    ),
                ]
            )
            await sess.commit()
            incident_id = incident.id

        with _swap_validators(app, _make_partner_validator("acme-corp")):
            resp = await client.get(
                f"/api/v1/incidents/{incident_id}/activities",
                headers=registered_analyst["headers"],
            )

        # If the incident is cross-tenant-visible (spanning both partners),
        # response either blocks or filters activities to mine-only.
        assert resp.status_code in (200, 403)
        if resp.status_code == 200:
            details = {a["detail"] for a in resp.json()["activities"]}
            assert "foreign-only" not in details
