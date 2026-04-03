from __future__ import annotations

from types import ModuleType

from fastapi import FastAPI

from opensoar.plugins import (
    configure_alembic_version_locations,
    dispatch_audit_event,
    dispatch_api_key_validators,
    apply_tenant_access_query,
    enforce_tenant_access,
    get_auth_capabilities,
    get_plugin_migration_config,
    import_optional_plugin_models,
    load_optional_plugins,
    register_api_key_validator,
    register_audit_sink,
    register_tenant_access_validator,
)
from opensoar.schemas.audit import AuditEvent


class FakeEntryPoint:
    def __init__(self, name: str, plugin, module: str | None = None):
        self.name = name
        self._plugin = plugin
        self.module = module

    def load(self):
        return self._plugin


def test_load_optional_plugins_no_plugins(monkeypatch):
    app = FastAPI()
    monkeypatch.setattr("opensoar.plugins.iter_plugin_entry_points", lambda group="opensoar.plugins": [])

    loaded = load_optional_plugins(app)

    assert loaded == []
    assert get_auth_capabilities(app) == {
        "local_login_enabled": True,
        "local_registration_enabled": True,
        "providers": [],
    }


def test_load_optional_plugins_registers_auth_provider(monkeypatch):
    app = FastAPI()

    def fake_plugin(target_app: FastAPI):
        target_app.state.local_auth_enabled = False
        target_app.state.local_registration_enabled = False
        target_app.state.auth_providers = [
            {
                "id": "oidc-okta",
                "name": "Okta",
                "type": "oidc",
                "login_url": "/api/v1/sso/oidc/authorize?provider_id=oidc-okta",
            }
        ]

    monkeypatch.setattr(
        "opensoar.plugins.iter_plugin_entry_points",
        lambda group="opensoar.plugins": [FakeEntryPoint("ee", fake_plugin)],
    )

    loaded = load_optional_plugins(app)

    assert loaded == ["ee"]
    assert get_auth_capabilities(app) == {
        "local_login_enabled": False,
        "local_registration_enabled": False,
        "providers": [
            {
                "id": "oidc-okta",
                "name": "Okta",
                "type": "oidc",
                "login_url": "/api/v1/sso/oidc/authorize?provider_id=oidc-okta",
            }
        ],
    }


def test_get_plugin_migration_config_no_plugins(monkeypatch):
    monkeypatch.setattr(
        "opensoar.plugins.iter_plugin_entry_points",
        lambda group="opensoar.plugins": [],
    )

    config = get_plugin_migration_config()

    assert config.model_modules == ()
    assert config.version_locations == ()


def test_get_plugin_migration_config_collects_models_and_versions(monkeypatch, tmp_path):
    plugin_file = tmp_path / "opensoar_ee" / "__init__.py"
    plugin_file.parent.mkdir()
    plugin_file.write_text("# plugin module\n")

    plugin_module = ModuleType("opensoar_ee")
    plugin_module.__file__ = str(plugin_file)
    plugin_module.PLUGIN_MODEL_MODULES = ("opensoar_ee.models",)
    plugin_module.PLUGIN_VERSION_LOCATIONS = ("migrations/versions",)

    imported_modules: dict[str, ModuleType] = {
        "opensoar_ee": plugin_module,
        "opensoar_ee.models": ModuleType("opensoar_ee.models"),
    }

    def fake_import_module(name: str):
        return imported_modules[name]

    def fake_plugin(_app: FastAPI):
        return None

    monkeypatch.setattr(
        "opensoar.plugins.iter_plugin_entry_points",
        lambda group="opensoar.plugins": [
            FakeEntryPoint("ee", fake_plugin, module="opensoar_ee")
        ],
    )
    monkeypatch.setattr("opensoar.plugins.importlib.import_module", fake_import_module)

    config = get_plugin_migration_config()
    imported = import_optional_plugin_models()

    assert config.model_modules == ("opensoar_ee.models",)
    assert config.version_locations == (
        str((plugin_file.parent / "migrations" / "versions").resolve()),
    )
    assert imported == ("opensoar_ee.models",)


def test_configure_alembic_version_locations():
    class FakeConfig:
        def __init__(self):
            self.values: dict[str, str] = {}

        def set_main_option(self, key: str, value: str):
            self.values[key] = value

    config = FakeConfig()
    result = configure_alembic_version_locations(
        config,
        core_versions_path="/core/versions",
        plugin_version_locations=("/ee/versions",),
    )

    assert result == ("/core/versions", "/ee/versions")
    assert config.values["version_locations"] == "/core/versions:/ee/versions"


async def test_dispatch_audit_event_calls_registered_sink():
    app = FastAPI()
    seen: list[AuditEvent] = []

    async def sink(event: AuditEvent):
        seen.append(event)

    register_audit_sink(app, sink)
    event = AuditEvent(category="auth", action="analyst.logged_in", actor_username="alice")

    await dispatch_audit_event(app, event)

    assert len(seen) == 1
    assert seen[0].action == "analyst.logged_in"


async def test_dispatch_api_key_validators_calls_registered_validator():
    app = FastAPI()
    seen = []

    async def validator(*, api_key, request, required_scope):
        seen.append((api_key, request, required_scope))

    register_api_key_validator(app, validator)
    await dispatch_api_key_validators(
        app,
        api_key="db-key",
        request="request",
        required_scope="webhooks:ingest",
    )

    assert seen == [("db-key", "request", "webhooks:ingest")]


async def test_tenant_access_validator_can_modify_query_and_validate_resource():
    app = FastAPI()
    seen = []

    async def validator(**kwargs):
        seen.append(kwargs["action"])
        if "query" in kwargs:
            return f"{kwargs['query']}-scoped"
        if kwargs["resource"] == "blocked":
            raise ValueError("blocked")

    register_tenant_access_validator(app, validator)

    scoped_query = await apply_tenant_access_query(
        app,
        query="query",
        resource_type="alert",
        action="list",
        analyst="analyst",
        request="request",
        session="session",
    )
    assert scoped_query == "query-scoped"

    await enforce_tenant_access(
        app,
        resource="allowed",
        resource_type="alert",
        action="read",
        analyst="analyst",
        request="request",
        session="session",
    )

    assert seen == ["list", "read"]
