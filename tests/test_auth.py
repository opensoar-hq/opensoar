"""Tests for authentication — JWT, registration, login."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from opensoar.auth.jwt import create_access_token, decode_token
from opensoar.config import settings


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
