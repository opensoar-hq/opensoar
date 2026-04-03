from __future__ import annotations

from fastapi import FastAPI

from opensoar.plugins import get_auth_capabilities, load_optional_plugins


class FakeEntryPoint:
    def __init__(self, name: str, plugin):
        self.name = name
        self._plugin = plugin

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
