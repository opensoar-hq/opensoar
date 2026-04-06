from __future__ import annotations

import importlib
import inspect
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from types import ModuleType
from typing import Any

from fastapi import FastAPI

from opensoar.auth.rbac import CORE_ANALYST_ROLE_LABELS
from opensoar.schemas.audit import AuditEvent

logger = logging.getLogger(__name__)

PLUGIN_GROUP = "opensoar.plugins"
PLUGIN_MODEL_MODULES_ATTR = "PLUGIN_MODEL_MODULES"
PLUGIN_VERSION_LOCATIONS_ATTR = "PLUGIN_VERSION_LOCATIONS"


def initialize_plugin_state(app: FastAPI) -> None:
    """Initialize shared plugin state once so optional packages can extend it."""
    if not hasattr(app.state, "analyst_roles"):
        app.state.analyst_roles = [
            {"id": role_id, "label": label}
            for role_id, label in CORE_ANALYST_ROLE_LABELS.items()
        ]
    if not hasattr(app.state, "auth_providers"):
        app.state.auth_providers = []
    if not hasattr(app.state, "audit_sinks"):
        app.state.audit_sinks = []
    if not hasattr(app.state, "api_key_validators"):
        app.state.api_key_validators = []
    if not hasattr(app.state, "tenant_access_validators"):
        app.state.tenant_access_validators = []
    if not hasattr(app.state, "local_auth_enabled"):
        app.state.local_auth_enabled = True
    if not hasattr(app.state, "local_registration_enabled"):
        app.state.local_registration_enabled = False


def iter_plugin_entry_points(group: str = PLUGIN_GROUP) -> Iterable[Any]:
    discovered = entry_points()
    if hasattr(discovered, "select"):
        return discovered.select(group=group)
    return discovered.get(group, [])


@dataclass(frozen=True)
class PluginMigrationConfig:
    model_modules: tuple[str, ...] = ()
    version_locations: tuple[str, ...] = ()


def _load_plugin_module(plugin_ep: Any) -> ModuleType:
    plugin = plugin_ep.load()
    module_name = getattr(plugin_ep, "module", None) or getattr(plugin, "__module__", None)
    if not module_name:
        raise ValueError(f"Unable to determine plugin module for entry point {plugin_ep.name}")
    return importlib.import_module(module_name)


def _normalize_version_location(module: ModuleType, location: str) -> str:
    path = Path(location)
    if path.is_absolute():
        return str(path)

    module_file = getattr(module, "__file__", None)
    if not module_file:
        raise ValueError(
            f"Plugin module {module.__name__} must define __file__ for relative version paths"
        )
    return str((Path(module_file).resolve().parent / path).resolve())


def get_plugin_migration_config(group: str = PLUGIN_GROUP) -> PluginMigrationConfig:
    model_modules: list[str] = []
    version_locations: list[str] = []

    for plugin_ep in iter_plugin_entry_points(group):
        module = _load_plugin_module(plugin_ep)

        for model_module in getattr(module, PLUGIN_MODEL_MODULES_ATTR, ()):
            if model_module not in model_modules:
                model_modules.append(model_module)

        for location in getattr(module, PLUGIN_VERSION_LOCATIONS_ATTR, ()):
            normalized = _normalize_version_location(module, location)
            if normalized not in version_locations:
                version_locations.append(normalized)

    return PluginMigrationConfig(
        model_modules=tuple(model_modules),
        version_locations=tuple(version_locations),
    )


def import_optional_plugin_models(group: str = PLUGIN_GROUP) -> tuple[str, ...]:
    config = get_plugin_migration_config(group)
    imported: list[str] = []
    for model_module in config.model_modules:
        importlib.import_module(model_module)
        imported.append(model_module)
    return tuple(imported)


def configure_alembic_version_locations(
    alembic_config: Any,
    *,
    core_versions_path: str,
    plugin_version_locations: Iterable[str],
) -> tuple[str, ...]:
    version_locations = [core_versions_path, *plugin_version_locations]
    alembic_config.set_main_option("version_locations", os.pathsep.join(version_locations))
    return tuple(version_locations)


def load_optional_plugins(app: FastAPI, group: str = PLUGIN_GROUP) -> list[str]:
    initialize_plugin_state(app)

    loaded_plugins: list[str] = []
    for plugin_ep in iter_plugin_entry_points(group):
        try:
            plugin = plugin_ep.load()
            plugin(app)
            loaded_plugins.append(plugin_ep.name)
            logger.info("Loaded optional plugin: %s", plugin_ep.name)
        except Exception:
            logger.exception("Failed to load optional plugin: %s", plugin_ep.name)

    return loaded_plugins


def configure_local_auth(
    app: FastAPI,
    *,
    login_enabled: bool | None = None,
    registration_enabled: bool | None = None,
) -> None:
    initialize_plugin_state(app)
    if login_enabled is not None:
        app.state.local_auth_enabled = login_enabled
    if registration_enabled is not None:
        app.state.local_registration_enabled = registration_enabled


def register_analyst_role(
    app: FastAPI,
    *,
    role: str,
    label: str | None = None,
) -> None:
    initialize_plugin_state(app)

    roles = [
        item for item in app.state.analyst_roles if item["id"] != role
    ]
    roles.append(
        {
            "id": role,
            "label": label or role.replace("_", " ").title(),
        }
    )
    app.state.analyst_roles = roles


def get_analyst_roles(app: FastAPI) -> list[dict[str, str]]:
    initialize_plugin_state(app)
    return list(app.state.analyst_roles)


def register_auth_provider(
    app: FastAPI,
    *,
    provider_id: str,
    name: str,
    provider_type: str,
    login_url: str | None = None,
) -> None:
    initialize_plugin_state(app)

    providers = [
        provider for provider in app.state.auth_providers if provider["id"] != provider_id
    ]
    providers.append(
        {
            "id": provider_id,
            "name": name,
            "type": provider_type,
            "login_url": login_url,
        }
    )
    app.state.auth_providers = providers


def register_audit_sink(app: FastAPI, sink: Any) -> None:
    initialize_plugin_state(app)
    app.state.audit_sinks.append(sink)


def register_api_key_validator(app: FastAPI, validator: Any) -> None:
    initialize_plugin_state(app)
    app.state.api_key_validators.append(validator)


def register_tenant_access_validator(app: FastAPI, validator: Any) -> None:
    initialize_plugin_state(app)
    app.state.tenant_access_validators.append(validator)


async def dispatch_audit_event(app: FastAPI, event: AuditEvent) -> None:
    initialize_plugin_state(app)
    for sink in list(app.state.audit_sinks):
        result = sink(event)
        if inspect.isawaitable(result):
            await result


async def dispatch_api_key_validators(
    app: FastAPI,
    *,
    api_key: Any,
    request: Any,
    required_scope: str,
) -> None:
    initialize_plugin_state(app)
    for validator in list(app.state.api_key_validators):
        result = validator(api_key=api_key, request=request, required_scope=required_scope)
        if inspect.isawaitable(result):
            await result


async def apply_tenant_access_query(
    app: FastAPI,
    *,
    query: Any,
    resource_type: str,
    action: str,
    analyst: Any,
    request: Any,
    session: Any,
):
    initialize_plugin_state(app)
    for validator in list(app.state.tenant_access_validators):
        result = validator(
            query=query,
            resource_type=resource_type,
            action=action,
            analyst=analyst,
            request=request,
            session=session,
        )
        if inspect.isawaitable(result):
            result = await result
        if result is not None:
            query = result
    return query


async def enforce_tenant_access(
    app: FastAPI,
    *,
    resource: Any,
    resource_type: str,
    action: str,
    analyst: Any,
    request: Any,
    session: Any,
) -> None:
    initialize_plugin_state(app)
    for validator in list(app.state.tenant_access_validators):
        result = validator(
            resource=resource,
            resource_type=resource_type,
            action=action,
            analyst=analyst,
            request=request,
            session=session,
        )
        if inspect.isawaitable(result):
            await result


def get_auth_capabilities(app: FastAPI) -> dict[str, Any]:
    initialize_plugin_state(app)
    return {
        "local_login_enabled": app.state.local_auth_enabled,
        "local_registration_enabled": app.state.local_registration_enabled,
        "providers": list(app.state.auth_providers),
    }
