"""Tests for playbook API — list, enable/disable, trigger engine respects enabled flag."""
from __future__ import annotations

from opensoar.core.decorators import PlaybookMeta, RegisteredPlaybook, _PLAYBOOK_REGISTRY
from opensoar.core.registry import PlaybookRegistry


class TestPlaybookEnableDisable:
    """The trigger engine should not match disabled playbooks."""

    def test_disabled_playbook_not_matched(self):
        """A playbook with enabled=False should not be returned by get_playbooks_for_trigger."""
        registry = PlaybookRegistry([])

        async def disabled_pb(alert):
            pass

        _PLAYBOOK_REGISTRY["test_disabled_pb"] = RegisteredPlaybook(
            meta=PlaybookMeta(
                name="test_disabled_pb",
                trigger="webhook",
                conditions={},
                enabled=False,
            ),
            func=disabled_pb,
            module="test",
        )

        matches = registry.get_playbooks_for_trigger("webhook", {})
        names = [m.meta.name for m in matches]
        assert "test_disabled_pb" not in names

        del _PLAYBOOK_REGISTRY["test_disabled_pb"]

    def test_enabled_playbook_matched(self):
        """A playbook with enabled=True should be returned by get_playbooks_for_trigger."""
        registry = PlaybookRegistry([])

        async def enabled_pb(alert):
            pass

        _PLAYBOOK_REGISTRY["test_enabled_pb"] = RegisteredPlaybook(
            meta=PlaybookMeta(
                name="test_enabled_pb",
                trigger="webhook",
                conditions={},
                enabled=True,
            ),
            func=enabled_pb,
            module="test",
        )

        matches = registry.get_playbooks_for_trigger("webhook", {})
        names = [m.meta.name for m in matches]
        assert "test_enabled_pb" in names

        del _PLAYBOOK_REGISTRY["test_enabled_pb"]

    def test_re_enable_playbook(self):
        """Toggling enabled back to True should make the playbook match again."""
        registry = PlaybookRegistry([])

        async def toggle_pb(alert):
            pass

        meta = PlaybookMeta(
            name="test_toggle_pb",
            trigger="webhook",
            conditions={},
            enabled=False,
        )
        _PLAYBOOK_REGISTRY["test_toggle_pb"] = RegisteredPlaybook(
            meta=meta, func=toggle_pb, module="test"
        )

        # Disabled — should not match this specific playbook
        matches = registry.get_playbooks_for_trigger("webhook", {})
        assert not any(m.meta.name == "test_toggle_pb" for m in matches)

        # Re-enable
        meta.enabled = True
        matches = registry.get_playbooks_for_trigger("webhook", {})
        assert any(m.meta.name == "test_toggle_pb" for m in matches)

        del _PLAYBOOK_REGISTRY["test_toggle_pb"]


class TestPlaybookAPI:
    """Integration tests for playbook CRUD endpoints."""

    async def test_list_playbooks(self, client, registered_analyst):
        resp = await client.get("/api/v1/playbooks", headers=registered_analyst["headers"])
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_playbooks_is_sorted_by_execution_order(self, client, db_session_factory, registered_analyst):
        from opensoar.models.playbook import PlaybookDefinition

        async with db_session_factory() as session:
            session.add_all([
                PlaybookDefinition(
                    name="ordered_second_api_pb",
                    execution_order=20,
                    module_path="test",
                    function_name="second_fn",
                    trigger_type="webhook",
                    trigger_config={},
                    enabled=True,
                ),
                PlaybookDefinition(
                    name="ordered_first_api_pb",
                    execution_order=10,
                    module_path="test",
                    function_name="first_fn",
                    trigger_type="webhook",
                    trigger_config={},
                    enabled=True,
                ),
            ])
            await session.commit()

        resp = await client.get("/api/v1/playbooks", headers=registered_analyst["headers"])
        assert resp.status_code == 200
        names = [pb["name"] for pb in resp.json() if pb["name"] in {"ordered_first_api_pb", "ordered_second_api_pb"}]
        assert names == ["ordered_first_api_pb", "ordered_second_api_pb"]

    async def test_update_playbook_enabled(self, client, db_session_factory, registered_admin):
        """PATCH /playbooks/{id} should toggle enabled field."""
        from opensoar.models.playbook import PlaybookDefinition

        # Create a playbook definition directly
        async with db_session_factory() as session:
            pb = PlaybookDefinition(
                name="test_toggle_api_pb",
                module_path="test",
                function_name="test_fn",
                trigger_type="webhook",
                trigger_config={},
                enabled=True,
            )
            session.add(pb)
            await session.commit()
            pb_id = pb.id

        # Disable via API
        resp = await client.patch(
            f"/api/v1/playbooks/{pb_id}",
            headers=registered_admin["headers"],
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

        # Re-enable
        resp = await client.patch(
            f"/api/v1/playbooks/{pb_id}",
            headers=registered_admin["headers"],
            json={"enabled": True},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True
