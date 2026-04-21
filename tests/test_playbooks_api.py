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


class TestClearAndReload:
    """Unit tests for the registry clear_and_reload helper (issue #112)."""

    def test_clear_and_reload_refreshes_registry(self, tmp_path):
        """Writing a playbook, reloading, mutating it, then reloading should
        reflect the new metadata in the registry."""
        import os

        from opensoar.core.decorators import _PLAYBOOK_REGISTRY, get_playbook_registry

        pb_dir = tmp_path / "reload_pbs"
        pb_dir.mkdir()
        (pb_dir / "__init__.py").write_text("")

        pb_file = pb_dir / "sample_reload_pb.py"
        pb_file.write_text(
            "from opensoar import playbook\n"
            "\n"
            "@playbook(trigger='webhook', description='v1')\n"
            "async def sample_reload_pb(alert):\n"
            "    return {'version': 1}\n"
        )
        # Backdate the file so a second-resolution mtime change is visible
        os.utime(pb_file, (1_000_000_000, 1_000_000_000))

        # Ensure any prior entry is gone
        _PLAYBOOK_REGISTRY.pop("sample_reload_pb", None)

        registry = PlaybookRegistry([str(pb_dir)])
        count = registry.clear_and_reload()
        assert count >= 1
        assert "sample_reload_pb" in get_playbook_registry()
        assert get_playbook_registry()["sample_reload_pb"].meta.description == "v1"

        # Mutate the playbook on disk (force a later mtime so source cache invalidates)
        pb_file.write_text(
            "from opensoar import playbook\n"
            "\n"
            "@playbook(trigger='webhook', description='v2')\n"
            "async def sample_reload_pb(alert):\n"
            "    return {'version': 2}\n"
        )
        os.utime(pb_file, (2_000_000_000, 2_000_000_000))

        count = registry.clear_and_reload()
        assert count >= 1
        assert get_playbook_registry()["sample_reload_pb"].meta.description == "v2"

        _PLAYBOOK_REGISTRY.pop("sample_reload_pb", None)

    def test_clear_and_reload_drops_removed_playbooks(self, tmp_path):
        """Playbooks that no longer exist on disk should be removed after reload."""
        from opensoar.core.decorators import _PLAYBOOK_REGISTRY, get_playbook_registry

        pb_dir = tmp_path / "reload_pbs_remove"
        pb_dir.mkdir()
        (pb_dir / "__init__.py").write_text("")

        pb_file = pb_dir / "ephemeral_pb.py"
        pb_file.write_text(
            "from opensoar import playbook\n"
            "\n"
            "@playbook(trigger='webhook')\n"
            "async def ephemeral_pb(alert):\n"
            "    return {}\n"
        )

        _PLAYBOOK_REGISTRY.pop("ephemeral_pb", None)

        registry = PlaybookRegistry([str(pb_dir)])
        registry.clear_and_reload()
        assert "ephemeral_pb" in get_playbook_registry()

        # Delete the file and reload — registry should no longer contain it
        pb_file.unlink()
        registry.clear_and_reload()
        assert "ephemeral_pb" not in get_playbook_registry()


class TestReloadEndpoint:
    """Integration tests for POST /api/v1/playbooks/reload (issue #112)."""

    async def test_reload_requires_auth(self, client):
        """Unauthenticated requests must be rejected."""
        resp = await client.post("/api/v1/playbooks/reload")
        assert resp.status_code == 401

    async def test_reload_requires_admin(self, client, registered_analyst):
        """Non-admin analysts lack PLAYBOOKS_MANAGE and must be rejected."""
        resp = await client.post(
            "/api/v1/playbooks/reload",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 403

    async def test_reload_refreshes_registry(self, client, registered_admin, tmp_path, monkeypatch):
        """Admin POST should re-scan the playbook dirs and return a count."""
        import os

        from opensoar.core.decorators import _PLAYBOOK_REGISTRY, get_playbook_registry

        pb_dir = tmp_path / "endpoint_pbs"
        pb_dir.mkdir()
        (pb_dir / "__init__.py").write_text("")

        pb_file = pb_dir / "endpoint_reload_pb.py"
        pb_file.write_text(
            "from opensoar import playbook\n"
            "\n"
            "@playbook(trigger='webhook', description='v1')\n"
            "async def endpoint_reload_pb(alert):\n"
            "    return {'version': 1}\n"
        )
        os.utime(pb_file, (1_000_000_000, 1_000_000_000))

        _PLAYBOOK_REGISTRY.pop("endpoint_reload_pb", None)

        # Point the endpoint at our temporary playbook dir
        from opensoar.config import settings
        monkeypatch.setattr(
            type(settings),
            "playbook_directories",
            property(lambda self: [str(pb_dir)]),
        )

        resp = await client.post(
            "/api/v1/playbooks/reload",
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "count" in body
        assert body["count"] >= 1
        assert "endpoint_reload_pb" in get_playbook_registry()
        assert get_playbook_registry()["endpoint_reload_pb"].meta.description == "v1"

        # Mutate on disk and reload again (force later mtime)
        pb_file.write_text(
            "from opensoar import playbook\n"
            "\n"
            "@playbook(trigger='webhook', description='v2')\n"
            "async def endpoint_reload_pb(alert):\n"
            "    return {'version': 2}\n"
        )
        os.utime(pb_file, (2_000_000_000, 2_000_000_000))

        resp = await client.post(
            "/api/v1/playbooks/reload",
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 200
        assert get_playbook_registry()["endpoint_reload_pb"].meta.description == "v2"

        _PLAYBOOK_REGISTRY.pop("endpoint_reload_pb", None)
