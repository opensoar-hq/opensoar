from __future__ import annotations

import logging
from collections.abc import Iterable
from importlib.metadata import entry_points
from typing import Any

from fastapi import FastAPI

logger = logging.getLogger(__name__)

PLUGIN_GROUP = "opensoar.plugins"


def initialize_plugin_state(app: FastAPI) -> None:
    """Initialize shared plugin state once so optional packages can extend it."""
    if not hasattr(app.state, "auth_providers"):
        app.state.auth_providers = []
    if not hasattr(app.state, "local_auth_enabled"):
        app.state.local_auth_enabled = True
    if not hasattr(app.state, "local_registration_enabled"):
        app.state.local_registration_enabled = True


def iter_plugin_entry_points(group: str = PLUGIN_GROUP) -> Iterable[Any]:
    discovered = entry_points()
    if hasattr(discovered, "select"):
        return discovered.select(group=group)
    return discovered.get(group, [])


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


def get_auth_capabilities(app: FastAPI) -> dict[str, Any]:
    initialize_plugin_state(app)
    return {
        "local_login_enabled": app.state.local_auth_enabled,
        "local_registration_enabled": app.state.local_registration_enabled,
        "providers": list(app.state.auth_providers),
    }
