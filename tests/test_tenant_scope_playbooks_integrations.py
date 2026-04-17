"""Tenant scoping tests for playbooks and integrations.

Covers the tenant_id model field, list filtering through registered
tenant_access_validators, enforce_tenant_access on write paths, and the
global (tenant_id=None) escape hatch that keeps built-ins visible to every
tenant.  Mirrors the patterns proven out for alerts/incidents/observables.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException

from opensoar.plugins import register_tenant_access_validator


def _swap_validators(app, *validators):
    """Context helper that replaces the registered validators and restores them."""

    class _Swap:
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

    return _Swap(app, validators)


class TestPlaybookTenantScope:
    async def test_playbook_model_accepts_tenant_id(self, session):
        from opensoar.models.playbook import PlaybookDefinition

        tenant_id = uuid.uuid4()
        pb = PlaybookDefinition(
            name=f"tenant_pb_{uuid.uuid4().hex[:6]}",
            module_path="test",
            function_name="fn",
            trigger_type="webhook",
            trigger_config={},
            enabled=True,
            tenant_id=tenant_id,
        )
        session.add(pb)
        await session.commit()
        await session.refresh(pb)

        assert pb.tenant_id == tenant_id

    async def test_playbook_tenant_id_nullable_means_global(self, session):
        from opensoar.models.playbook import PlaybookDefinition

        pb = PlaybookDefinition(
            name=f"global_pb_{uuid.uuid4().hex[:6]}",
            module_path="test",
            function_name="fn",
            trigger_type="webhook",
            trigger_config={},
            enabled=True,
        )
        session.add(pb)
        await session.commit()
        await session.refresh(pb)

        assert pb.tenant_id is None

    async def test_list_filters_by_tenant_validator_but_keeps_globals(
        self, client, db_session_factory, registered_analyst
    ):
        from opensoar.main import app
        from opensoar.models.playbook import PlaybookDefinition

        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        async with db_session_factory() as sess:
            sess.add_all(
                [
                    PlaybookDefinition(
                        name=f"scope_global_{uuid.uuid4().hex[:6]}",
                        module_path="test",
                        function_name="fn",
                        trigger_type="webhook",
                        trigger_config={},
                        enabled=True,
                    ),
                    PlaybookDefinition(
                        name=f"scope_a_{uuid.uuid4().hex[:6]}",
                        module_path="test",
                        function_name="fn",
                        trigger_type="webhook",
                        trigger_config={},
                        enabled=True,
                        tenant_id=tenant_a,
                    ),
                    PlaybookDefinition(
                        name=f"scope_b_{uuid.uuid4().hex[:6]}",
                        module_path="test",
                        function_name="fn",
                        trigger_type="webhook",
                        trigger_config={},
                        enabled=True,
                        tenant_id=tenant_b,
                    ),
                ]
            )
            await sess.commit()

        async def validator(**kwargs):
            query = kwargs.get("query")
            if query is not None and kwargs["resource_type"] == "playbook":
                from sqlalchemy import or_

                return query.where(
                    or_(
                        PlaybookDefinition.tenant_id.is_(None),
                        PlaybookDefinition.tenant_id == tenant_a,
                    )
                )
            return None

        with _swap_validators(app, validator):
            resp = await client.get(
                "/api/v1/playbooks", headers=registered_analyst["headers"]
            )

        assert resp.status_code == 200
        returned = {pb["name"]: pb for pb in resp.json()}
        # Global and tenant_a rows are visible, tenant_b is filtered out.
        assert any(n.startswith("scope_global_") for n in returned)
        assert any(n.startswith("scope_a_") for n in returned)
        assert not any(n.startswith("scope_b_") for n in returned)

    async def test_update_rejects_cross_tenant_writes(
        self, client, db_session_factory, registered_admin
    ):
        from opensoar.main import app
        from opensoar.models.playbook import PlaybookDefinition

        other_tenant = uuid.uuid4()

        async with db_session_factory() as sess:
            pb = PlaybookDefinition(
                name=f"cross_tenant_{uuid.uuid4().hex[:6]}",
                module_path="test",
                function_name="fn",
                trigger_type="webhook",
                trigger_config={},
                enabled=True,
                tenant_id=other_tenant,
            )
            sess.add(pb)
            await sess.commit()
            pb_id = pb.id

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is None:
                return None
            tenant = getattr(resource, "tenant_id", None)
            if tenant is not None and tenant != uuid.UUID(int=0):
                raise HTTPException(status_code=403, detail="Tenant access denied")

        with _swap_validators(app, validator):
            resp = await client.patch(
                f"/api/v1/playbooks/{pb_id}",
                headers=registered_admin["headers"],
                json={"enabled": False},
            )

        assert resp.status_code == 403

    async def test_global_playbook_visible_to_other_tenants(
        self, client, db_session_factory, registered_analyst
    ):
        from opensoar.main import app
        from opensoar.models.playbook import PlaybookDefinition

        async with db_session_factory() as sess:
            pb = PlaybookDefinition(
                name=f"builtin_{uuid.uuid4().hex[:6]}",
                module_path="test",
                function_name="fn",
                trigger_type="webhook",
                trigger_config={},
                enabled=True,
            )
            sess.add(pb)
            await sess.commit()
            pb_id = pb.id
            pb_name = pb.name

        foreign_tenant = uuid.uuid4()

        async def validator(**kwargs):
            query = kwargs.get("query")
            if query is not None and kwargs["resource_type"] == "playbook":
                from sqlalchemy import or_

                return query.where(
                    or_(
                        PlaybookDefinition.tenant_id.is_(None),
                        PlaybookDefinition.tenant_id == foreign_tenant,
                    )
                )
            resource = kwargs.get("resource")
            if resource is not None:
                tenant = getattr(resource, "tenant_id", None)
                if tenant is not None and tenant != foreign_tenant:
                    raise HTTPException(status_code=403, detail="Tenant access denied")

        with _swap_validators(app, validator):
            list_resp = await client.get(
                "/api/v1/playbooks", headers=registered_analyst["headers"]
            )
            detail_resp = await client.get(
                f"/api/v1/playbooks/{pb_id}",
                headers=registered_analyst["headers"],
            )

        assert list_resp.status_code == 200
        assert any(pb["name"] == pb_name for pb in list_resp.json())
        assert detail_resp.status_code == 200
        assert detail_resp.json()["tenant_id"] is None


class TestIntegrationTenantScope:
    async def test_integration_model_accepts_tenant_id(self, session):
        from opensoar.models.integration import IntegrationInstance

        tenant_id = uuid.uuid4()
        integration = IntegrationInstance(
            integration_type="virustotal",
            name=f"VT {uuid.uuid4().hex[:6]}",
            config={"api_key": "x"},
            enabled=True,
            tenant_id=tenant_id,
        )
        session.add(integration)
        await session.commit()
        await session.refresh(integration)

        assert integration.tenant_id == tenant_id

    async def test_integration_tenant_id_nullable_means_global(self, session):
        from opensoar.models.integration import IntegrationInstance

        integration = IntegrationInstance(
            integration_type="slack",
            name=f"Slack {uuid.uuid4().hex[:6]}",
            config={},
            enabled=True,
        )
        session.add(integration)
        await session.commit()
        await session.refresh(integration)

        assert integration.tenant_id is None

    async def test_list_filters_by_tenant_but_keeps_globals(
        self, client, db_session_factory, registered_admin
    ):
        from opensoar.main import app
        from opensoar.models.integration import IntegrationInstance

        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        async with db_session_factory() as sess:
            sess.add_all(
                [
                    IntegrationInstance(
                        integration_type="slack",
                        name=f"global_int_{uuid.uuid4().hex[:6]}",
                        config={},
                        enabled=True,
                    ),
                    IntegrationInstance(
                        integration_type="slack",
                        name=f"tenant_a_int_{uuid.uuid4().hex[:6]}",
                        config={},
                        enabled=True,
                        tenant_id=tenant_a,
                    ),
                    IntegrationInstance(
                        integration_type="slack",
                        name=f"tenant_b_int_{uuid.uuid4().hex[:6]}",
                        config={},
                        enabled=True,
                        tenant_id=tenant_b,
                    ),
                ]
            )
            await sess.commit()

        async def validator(**kwargs):
            query = kwargs.get("query")
            if query is not None and kwargs["resource_type"] == "integration":
                from sqlalchemy import or_

                return query.where(
                    or_(
                        IntegrationInstance.tenant_id.is_(None),
                        IntegrationInstance.tenant_id == tenant_a,
                    )
                )
            return None

        with _swap_validators(app, validator):
            resp = await client.get(
                "/api/v1/integrations", headers=registered_admin["headers"]
            )

        assert resp.status_code == 200
        names = {i["name"] for i in resp.json()}
        assert any(n.startswith("global_int_") for n in names)
        assert any(n.startswith("tenant_a_int_") for n in names)
        assert not any(n.startswith("tenant_b_int_") for n in names)

    async def test_update_rejects_cross_tenant_writes(
        self, client, db_session_factory, registered_admin
    ):
        from opensoar.main import app
        from opensoar.models.integration import IntegrationInstance

        other_tenant = uuid.uuid4()

        async with db_session_factory() as sess:
            integration = IntegrationInstance(
                integration_type="slack",
                name=f"other_tenant_int_{uuid.uuid4().hex[:6]}",
                config={},
                enabled=True,
                tenant_id=other_tenant,
            )
            sess.add(integration)
            await sess.commit()
            integration_id = integration.id

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is None:
                return None
            tenant = getattr(resource, "tenant_id", None)
            if tenant is not None:
                raise HTTPException(status_code=403, detail="Tenant access denied")

        with _swap_validators(app, validator):
            resp = await client.patch(
                f"/api/v1/integrations/{integration_id}",
                headers=registered_admin["headers"],
                json={"enabled": False},
            )

        assert resp.status_code == 403

    async def test_create_respects_tenant_validator_chain(
        self, client, registered_admin
    ):
        from opensoar.main import app

        called: list[str] = []

        async def validator(**kwargs):
            if kwargs.get("resource") is not None:
                called.append(kwargs["action"])

        with _swap_validators(app, validator):
            resp = await client.post(
                "/api/v1/integrations",
                headers=registered_admin["headers"],
                json={
                    "integration_type": "slack",
                    "name": f"tenant_create_{uuid.uuid4().hex[:6]}",
                    "config": {},
                },
            )

        assert resp.status_code == 201
        assert "create" in called

    async def test_global_integration_visible_to_tenants(
        self, client, db_session_factory, registered_admin
    ):
        from opensoar.main import app
        from opensoar.models.integration import IntegrationInstance

        async with db_session_factory() as sess:
            integration = IntegrationInstance(
                integration_type="slack",
                name=f"seeded_global_{uuid.uuid4().hex[:6]}",
                config={},
                enabled=True,
            )
            sess.add(integration)
            await sess.commit()
            integration_id = integration.id
            integration_name = integration.name

        foreign_tenant = uuid.uuid4()

        async def validator(**kwargs):
            query = kwargs.get("query")
            if query is not None and kwargs["resource_type"] == "integration":
                from sqlalchemy import or_

                return query.where(
                    or_(
                        IntegrationInstance.tenant_id.is_(None),
                        IntegrationInstance.tenant_id == foreign_tenant,
                    )
                )
            resource = kwargs.get("resource")
            if resource is not None:
                tenant = getattr(resource, "tenant_id", None)
                if tenant is not None and tenant != foreign_tenant:
                    raise HTTPException(status_code=403, detail="Tenant access denied")

        with _swap_validators(app, validator):
            list_resp = await client.get(
                "/api/v1/integrations", headers=registered_admin["headers"]
            )
            detail_resp = await client.get(
                f"/api/v1/integrations/{integration_id}",
                headers=registered_admin["headers"],
            )

        assert list_resp.status_code == 200
        assert any(i["name"] == integration_name for i in list_resp.json())
        assert detail_resp.status_code == 200
        assert detail_resp.json()["tenant_id"] is None
