"""Tests for authentication — JWT, registration, login."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from opensoar.auth.jwt import create_access_token, decode_token
from opensoar.config import settings
from opensoar.plugins import register_audit_sink


# ── JWT token tests ─────────────────────────────────────────


class TestJWT:
    def test_create_and_decode(self):
        analyst_id = uuid.uuid4()
        token = create_access_token(analyst_id, "testuser")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        assert payload["sub"] == str(analyst_id)
        assert payload["username"] == "testuser"

    def test_expired_token(self):
        payload = {
            "sub": str(uuid.uuid4()),
            "username": "expired",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
        with pytest.raises(Exception, match="Token expired"):
            decode_token(token)

    def test_invalid_token(self):
        with pytest.raises(Exception, match="Invalid token"):
            decode_token("not.a.valid.token")


# ── Registration endpoint ───────────────────────────────────


class TestRegister:
    async def test_register_success(self, client):
        username = f"newuser_{uuid.uuid4().hex[:8]}"
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "display_name": "New User",
                "password": "securepass123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["analyst"]["username"] == username

    async def test_register_rejects_unknown_role(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": f"badrole_{uuid.uuid4().hex[:8]}",
                "display_name": "Bad Role",
                "password": "securepass123",
                "role": "superuser",
            },
        )
        assert resp.status_code == 422

    async def test_register_duplicate_username(self, client):
        username = f"dup_{uuid.uuid4().hex[:8]}"
        body = {
            "username": username,
            "display_name": "Dup User",
            "password": "pass123",
        }
        await client.post("/api/v1/auth/register", json=body)
        resp = await client.post("/api/v1/auth/register", json=body)
        assert resp.status_code == 409

    async def test_register_disabled_when_local_registration_off(self, client):
        from opensoar.main import app
        from opensoar.plugins import configure_local_auth

        original_login = app.state.local_auth_enabled
        original_registration = app.state.local_registration_enabled
        try:
            configure_local_auth(app, registration_enabled=False)
            resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": f"blocked_{uuid.uuid4().hex[:8]}",
                    "display_name": "Blocked User",
                    "password": "securepass123",
                },
            )
        finally:
            app.state.local_auth_enabled = original_login
            app.state.local_registration_enabled = original_registration

        assert resp.status_code == 403

    async def test_register_emits_audit_event(self, client):
        from opensoar.main import app

        seen = []

        async def sink(event):
            seen.append(event)

        original_sinks = list(app.state.audit_sinks)
        app.state.audit_sinks = []
        register_audit_sink(app, sink)
        try:
            username = f"audit_{uuid.uuid4().hex[:8]}"
            resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": username,
                    "display_name": "Audit User",
                    "password": "securepass123",
                },
            )
        finally:
            app.state.audit_sinks = original_sinks

        assert resp.status_code == 200
        assert len(seen) == 1
        assert seen[0].action == "analyst.registered"
        assert seen[0].category == "auth"


# ── Login endpoint ──────────────────────────────────────────


class TestLogin:
    async def test_login_success(self, client):
        username = f"login_{uuid.uuid4().hex[:8]}"
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "display_name": "Login User",
                "password": "mypassword",
            },
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "mypassword"},
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    async def test_login_wrong_password(self, client):
        username = f"wrongpw_{uuid.uuid4().hex[:8]}"
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "display_name": "WrongPW",
                "password": "correct",
            },
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "wrong"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "pass"},
        )
        assert resp.status_code == 401

    async def test_login_without_local_password_rejected(self, client, session):
        from opensoar.models.analyst import Analyst

        analyst = Analyst(
            username=f"sso_{uuid.uuid4().hex[:8]}",
            display_name="SSO Only",
            email="sso@opensoar.app",
            password_hash=None,
            role="analyst",
        )
        session.add(analyst)
        await session.commit()

        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": analyst.username, "password": "any-password"},
        )
        assert resp.status_code == 401

    async def test_login_disabled_when_local_login_off(self, client):
        from opensoar.main import app
        from opensoar.plugins import configure_local_auth

        original_login = app.state.local_auth_enabled
        original_registration = app.state.local_registration_enabled
        try:
            configure_local_auth(app, login_enabled=False)
            resp = await client.post(
                "/api/v1/auth/login",
                json={"username": "nobody", "password": "pass"},
            )
        finally:
            app.state.local_auth_enabled = original_login
            app.state.local_registration_enabled = original_registration

        assert resp.status_code == 403

    async def test_login_emits_audit_event(self, client):
        from opensoar.main import app

        username = f"login_audit_{uuid.uuid4().hex[:8]}"
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "display_name": "Login Audit User",
                "password": "mypassword",
            },
        )

        seen = []

        async def sink(event):
            seen.append(event)

        original_sinks = list(app.state.audit_sinks)
        app.state.audit_sinks = []
        register_audit_sink(app, sink)
        try:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": "mypassword"},
            )
        finally:
            app.state.audit_sinks = original_sinks

        assert resp.status_code == 200
        assert len(seen) == 1
        assert seen[0].action == "analyst.logged_in"


# ── /me endpoint ────────────────────────────────────────────


class TestMe:
    async def test_me_authenticated(self, client):
        username = f"me_{uuid.uuid4().hex[:8]}"
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "display_name": "Me User",
                "password": "pass123",
            },
        )
        token = reg.json()["access_token"]
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == username

    async def test_me_unauthenticated(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestCapabilities:
    async def test_capabilities_default_local_auth(self, client):
        resp = await client.get("/api/v1/auth/capabilities")

        assert resp.status_code == 200
        assert resp.json() == {
            "local_login_enabled": True,
            "local_registration_enabled": True,
            "providers": [],
        }

    async def test_capabilities_reflect_app_state(self, client):
        from opensoar.main import app

        original_login = app.state.local_auth_enabled
        original_registration = app.state.local_registration_enabled
        original_providers = list(app.state.auth_providers)

        app.state.local_auth_enabled = False
        app.state.local_registration_enabled = False
        app.state.auth_providers = [
            {
                "id": "oidc-keycloak",
                "name": "Keycloak",
                "type": "oidc",
                "login_url": "/api/v1/sso/oidc/authorize?provider_id=oidc-keycloak",
            }
        ]

        try:
            resp = await client.get("/api/v1/auth/capabilities")
        finally:
            app.state.local_auth_enabled = original_login
            app.state.local_registration_enabled = original_registration
            app.state.auth_providers = original_providers

        assert resp.status_code == 200
        assert resp.json() == {
            "local_login_enabled": False,
            "local_registration_enabled": False,
            "providers": [
                {
                    "id": "oidc-keycloak",
                    "name": "Keycloak",
                    "type": "oidc",
                    "login_url": "/api/v1/sso/oidc/authorize?provider_id=oidc-keycloak",
                }
            ],
        }


class TestExternalIdentities:
    async def test_external_identity_can_be_persisted(self, session):
        from opensoar.models.analyst import Analyst
        from opensoar.models.analyst_identity import AnalystIdentity

        analyst = Analyst(
            username=f"linked_{uuid.uuid4().hex[:8]}",
            display_name="Linked Analyst",
            email="linked@opensoar.app",
            password_hash=None,
            role="analyst",
        )
        session.add(analyst)
        await session.flush()

        identity = AnalystIdentity(
            analyst_id=analyst.id,
            provider_type="oidc",
            issuer="https://idp.example.com",
            subject=f"user-{uuid.uuid4().hex[:8]}",
            email="linked@opensoar.app",
            claims_json={"groups": ["soc-analysts"]},
        )
        session.add(identity)
        await session.commit()

        result = await session.execute(
            select(AnalystIdentity).where(AnalystIdentity.id == identity.id)
        )
        stored = result.scalar_one()
        assert stored.analyst_id == analyst.id
        assert stored.provider_type == "oidc"


class TestAdminRoleUpdates:
    async def test_admin_can_assign_enterprise_roles(self, client, registered_admin, session):
        from opensoar.models.analyst import Analyst

        analyst = Analyst(
            username=f"role_target_{uuid.uuid4().hex[:8]}",
            display_name="Role Target",
            email="role.target@opensoar.app",
            password_hash="$2b$12$LJ3m4ys3Lz0Y1r2VQz5Zu.dummyhashnotreal000000000000000",
            role="analyst",
        )
        session.add(analyst)
        await session.commit()

        tenant_admin_resp = await client.patch(
            f"/api/v1/auth/analysts/{analyst.id}",
            headers=registered_admin["headers"],
            json={"role": "tenant_admin"},
        )
        assert tenant_admin_resp.status_code == 200
        assert tenant_admin_resp.json()["role"] == "tenant_admin"

        playbook_author_resp = await client.patch(
            f"/api/v1/auth/analysts/{analyst.id}",
            headers=registered_admin["headers"],
            json={"role": "playbook_author"},
        )
        assert playbook_author_resp.status_code == 200
        assert playbook_author_resp.json()["role"] == "playbook_author"

    async def test_admin_update_rejects_unknown_role(self, client, registered_admin, session):
        from opensoar.models.analyst import Analyst

        analyst = Analyst(
            username=f"unknown_role_target_{uuid.uuid4().hex[:8]}",
            display_name="Unknown Role Target",
            email="unknown.role.target@opensoar.app",
            password_hash="$2b$12$LJ3m4ys3Lz0Y1r2VQz5Zu.dummyhashnotreal000000000000000",
            role="analyst",
        )
        session.add(analyst)
        await session.commit()

        resp = await client.patch(
            f"/api/v1/auth/analysts/{analyst.id}",
            headers=registered_admin["headers"],
            json={"role": "superuser"},
        )
        assert resp.status_code == 422
