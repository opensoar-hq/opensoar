"""Tests for the 4 critical security fixes from OPE-3 audit."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from opensoar.models.api_key import ApiKey


# ── Fix 1: Webhook HMAC signature verification ──────────────────


class TestWebhookHMACVerification:
    """Webhook endpoints should verify HMAC-SHA256 signatures when a secret is configured."""

    async def test_webhook_with_valid_hmac_signature(self, client, registered_admin):
        """Webhook should accept requests with a valid HMAC-SHA256 signature."""
        # Create an API key
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "hmac-test-key"},
            headers=registered_admin["headers"],
        )
        api_key = resp.json()["key"]

        payload = {"rule_name": "HMAC Test Alert", "severity": "high"}
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        signature = hmac.new(
            api_key.encode(), body.encode(), hashlib.sha256
        ).hexdigest()

        resp = await client.post(
            "/api/v1/webhooks/alerts",
            content=body,
            headers={
                "X-API-Key": api_key,
                "X-Webhook-Signature": f"sha256={signature}",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200

    async def test_webhook_with_invalid_hmac_signature(self, client, registered_admin):
        """Webhook should reject requests with an invalid HMAC signature."""
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "hmac-invalid-key"},
            headers=registered_admin["headers"],
        )
        api_key = resp.json()["key"]

        payload = {"rule_name": "Bad HMAC Alert", "severity": "low"}

        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json=payload,
            headers={
                "X-API-Key": api_key,
                "X-Webhook-Signature": "sha256=invalid_signature_here",
            },
        )
        assert resp.status_code == 401
        assert "signature" in resp.json()["detail"].lower()

    async def test_webhook_without_signature_still_works(self, client):
        """Webhook without signature header should still work (backward compat)."""
        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "No Sig Alert", "severity": "low"},
        )
        assert resp.status_code == 200


# ── Fix 2: JWT secret startup validation ────────────────────────


class TestJWTSecretValidation:
    """App should refuse to start if JWT_SECRET is empty."""

    def test_empty_jwt_secret_raises_on_settings_validation(self, monkeypatch):
        """Settings should reject empty jwt_secret."""
        from opensoar.config import Settings

        monkeypatch.delenv("JWT_SECRET", raising=False)
        monkeypatch.delenv("API_KEY_SECRET", raising=False)
        with pytest.raises(ValueError, match="[Jj][Ww][Tt]"):
            Settings(jwt_secret="", api_key_secret="test-key")

    def test_nonempty_jwt_secret_passes_validation(self, monkeypatch):
        """Settings should accept a non-empty jwt_secret."""
        from opensoar.config import Settings

        monkeypatch.delenv("JWT_SECRET", raising=False)
        monkeypatch.delenv("API_KEY_SECRET", raising=False)
        s = Settings(jwt_secret="a-real-secret", api_key_secret="test-key")
        assert s.jwt_secret == "a-real-secret"

    def test_empty_api_key_secret_raises_on_settings_validation(self, monkeypatch):
        """Settings should also reject empty api_key_secret."""
        from opensoar.config import Settings

        monkeypatch.delenv("JWT_SECRET", raising=False)
        monkeypatch.delenv("API_KEY_SECRET", raising=False)
        with pytest.raises(ValueError, match="[Aa][Pp][Ii]"):
            Settings(jwt_secret="ok-secret", api_key_secret="")

    def test_celery_broker_url_defaults_to_redis_url(self, monkeypatch):
        """Broker should fall back to redis_url when CELERY_BROKER_URL is unset."""
        from opensoar.config import Settings

        monkeypatch.delenv("JWT_SECRET", raising=False)
        monkeypatch.delenv("API_KEY_SECRET", raising=False)
        settings = Settings(
            jwt_secret="ok-secret",
            api_key_secret="test-key",
            redis_url="redis://localhost:6379/0",
        )
        assert settings.effective_celery_broker_url == "redis://localhost:6379/0"

    def test_celery_broker_url_override_is_honored(self, monkeypatch):
        """Broker should use CELERY_BROKER_URL when provided."""
        from opensoar.config import Settings

        monkeypatch.delenv("JWT_SECRET", raising=False)
        monkeypatch.delenv("API_KEY_SECRET", raising=False)
        settings = Settings(
            jwt_secret="ok-secret",
            api_key_secret="test-key",
            redis_url="redis://localhost:6379/0",
            celery_broker_url="redis://localhost:6379/1",
        )
        assert settings.effective_celery_broker_url == "redis://localhost:6379/1"


# ── Fix 3: API key expiry validation ────────────────────────────


class TestApiKeyExpiryValidation:
    """API key validation should reject expired keys."""

    async def test_expired_api_key_rejected(self, client, registered_admin, db_session_factory):
        """An API key past its expires_at should be rejected."""
        # Create an API key
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "expiry-test-key"},
            headers=registered_admin["headers"],
        )
        assert resp.status_code == 201
        api_key = resp.json()["key"]
        key_id = resp.json()["id"]

        # Set expires_at to the past directly in DB
        async with db_session_factory() as sess:
            result = await sess.execute(
                select(ApiKey).where(ApiKey.id == uuid.UUID(key_id))
            )
            db_key = result.scalar_one()
            db_key.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            await sess.commit()

        # Try to use the expired key
        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Expired Key Alert", "severity": "low"},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"].lower()

    async def test_non_expired_api_key_accepted(self, client, registered_admin, db_session_factory):
        """An API key with a future expires_at should be accepted."""
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "future-expiry-key"},
            headers=registered_admin["headers"],
        )
        api_key = resp.json()["key"]
        key_id = resp.json()["id"]

        # Set expires_at to the future
        async with db_session_factory() as sess:
            result = await sess.execute(
                select(ApiKey).where(ApiKey.id == uuid.UUID(key_id))
            )
            db_key = result.scalar_one()
            db_key.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            await sess.commit()

        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Valid Key Alert", "severity": "low"},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 200

    async def test_api_key_without_expiry_accepted(self, client, registered_admin):
        """An API key with no expires_at (None) should be accepted."""
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "no-expiry-key"},
            headers=registered_admin["headers"],
        )
        api_key = resp.json()["key"]

        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "No Expiry Alert", "severity": "low"},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 200


# ── Fix 4: Non-root Docker containers ───────────────────────────


class TestDockerfileNonRoot:
    """Dockerfile should define a non-root user for Python-based targets."""

    def test_dockerfile_has_non_root_user(self):
        """The Dockerfile should contain USER directives for non-root execution."""
        from pathlib import Path

        dockerfile = Path(__file__).resolve().parent.parent / "Dockerfile"
        content = dockerfile.read_text()

        # Should create a non-root user
        assert "useradd" in content or "adduser" in content or "addgroup" in content
        # Should have USER directive
        assert "USER" in content
        # Should NOT run as root
        lines = content.splitlines()
        user_lines = [line.strip() for line in lines if line.strip().startswith("USER")]
        assert len(user_lines) > 0
        for ul in user_lines:
            assert "root" not in ul.lower()
