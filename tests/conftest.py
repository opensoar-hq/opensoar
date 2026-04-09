"""Shared test fixtures for OpenSOAR test suite."""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

# Set required secrets before any opensoar imports (config validates on import)
os.environ.setdefault("JWT_SECRET", "test-secret-which-is-long-enough-for-hs256")
os.environ.setdefault("API_KEY_SECRET", "test-api-key-secret")
os.environ.setdefault("LOCAL_REGISTRATION_ENABLED", "true")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import opensoar.models  # noqa: F401 - load model definitions for the test app
from opensoar.plugins import import_optional_plugin_models

import_optional_plugin_models()

# Use DATABASE_URL env var if set (CI), otherwise default test DB
TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://opensoar:opensoar@localhost:5432/opensoar_test",
)


@pytest.fixture(scope="session")
async def db_engine():
    """Create engine and apply migrations once per session.

    Uses Alembic migrations (not Base.metadata.create_all) so tests exercise
    the same schema path as production.  This catches missing migrations early.
    Resets role-owned objects to recover from stale local DB state.
    """
    import subprocess

    eng = create_async_engine(TEST_DATABASE_URL, echo=False)

    async def reset_test_database() -> None:
        async with eng.begin() as conn:
            # The test database is dedicated to this role. Dropping everything
            # owned by the current user clears stale Alembic tables and relation
            # row types without requiring ownership of the public schema itself.
            await conn.execute(text("DROP OWNED BY CURRENT_USER CASCADE"))

    await reset_test_database()

    # Run Alembic migrations against the test database (same as production)
    project_root = os.path.join(os.path.dirname(__file__), "..")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=project_root,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Alembic migration failed:\n{result.stdout}\n{result.stderr}"
        )

    yield eng

    await reset_test_database()
    await eng.dispose()


@pytest.fixture(scope="session")
def db_session_factory(db_engine):
    """Session factory bound to the test engine."""
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def session(db_session_factory) -> AsyncGenerator[AsyncSession]:
    """Provide a test session for direct DB tests."""
    async with db_session_factory() as sess:
        yield sess


@pytest.fixture
async def client(db_session_factory) -> AsyncGenerator[AsyncClient]:
    """Provide a test HTTP client with its own DB session per request.

    Patches the trigger engine so webhook endpoints work without playbook discovery.
    """
    from opensoar.api.deps import get_db
    from opensoar.main import app

    async def override_get_db():
        async with db_session_factory() as sess:
            yield sess

    mock_engine = MagicMock()
    mock_engine.match.return_value = []

    app.dependency_overrides[get_db] = override_get_db

    with patch("opensoar.main.get_trigger_engine", return_value=mock_engine):
        with patch("opensoar.main._trigger_engine", mock_engine):
            from opensoar.middleware.rate_limit import reset_rate_limiter

            reset_rate_limiter()
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                yield c

    app.dependency_overrides.clear()


# ── API-based fixtures ──────────────────────────────────────


@pytest.fixture
async def registered_analyst(client: AsyncClient) -> dict:
    """Register a new analyst via the API."""
    username = f"test_{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "display_name": "Test Analyst",
            "email": "test@opensoar.app",
            "password": "testpassword123",
        },
    )
    data = resp.json()
    return {
        "token": data["access_token"],
        "analyst": data["analyst"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
    }


@pytest.fixture
async def registered_admin(session: AsyncSession) -> dict:
    """Create a new admin analyst directly in the DB."""
    from opensoar.api.auth import _hash_password
    from opensoar.models.analyst import Analyst
    from opensoar.auth.jwt import create_access_token

    analyst = Analyst(
        username=f"admin_{uuid.uuid4().hex[:8]}",
        display_name="Test Admin",
        email="admin@opensoar.app",
        password_hash=_hash_password("adminpass123"),
        role="admin",
        is_active=True,
    )
    session.add(analyst)
    await session.commit()
    await session.refresh(analyst)

    token = create_access_token(analyst.id, analyst.username)
    return {
        "token": token,
        "analyst": analyst,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
async def sample_alert_via_api(client: AsyncClient) -> dict:
    """Create a sample alert via the webhook API."""
    resp = await client.post(
        "/api/v1/webhooks/alerts",
        json={
            "rule_name": "Test Alert: Brute Force Detected",
            "severity": "high",
            "source_ip": "10.0.0.1",
            "hostname": "web-prod-01",
            "tags": ["authentication", "brute-force"],
            "partner": "acme-corp",
        },
    )
    return resp.json()


# ── Direct DB fixtures ──────────────────────────────────────


@pytest.fixture
async def analyst(session: AsyncSession):
    """Create a test analyst directly in DB."""
    from opensoar.models.analyst import Analyst

    a = Analyst(
        username=f"test_{uuid.uuid4().hex[:8]}",
        display_name="Test Analyst",
        email="test@opensoar.app",
        password_hash="$2b$12$LJ3m4ys3Lz0Y1r2VQz5Zu.dummyhashnotreal000000000000000",
        role="analyst",
    )
    session.add(a)
    await session.commit()
    return a


@pytest.fixture
def auth_headers(analyst) -> dict[str, str]:
    """Get auth headers for a test analyst."""
    from opensoar.auth.jwt import create_access_token

    token = create_access_token(analyst.id, analyst.username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def sample_alert(session: AsyncSession):
    """Create a sample alert directly in DB."""
    from opensoar.models.alert import Alert

    alert = Alert(
        source="webhook",
        source_id=f"test-{uuid.uuid4().hex[:8]}",
        title="Test Alert: Brute Force Detected",
        description="Multiple failed login attempts",
        severity="high",
        status="new",
        raw_payload={"rule_name": "Brute Force", "severity": "high", "source_ip": "10.0.0.1"},
        normalized={"severity": "high", "source": "webhook"},
        source_ip="10.0.0.1",
        hostname="web-prod-01",
        rule_name="Brute Force Detected",
        iocs={"ips": ["10.0.0.1"]},
        tags=["authentication", "brute-force"],
        partner="acme-corp",
    )
    session.add(alert)
    await session.commit()
    return alert
