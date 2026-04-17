from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from opensoar.middleware.metrics import MetricsMiddleware
from opensoar.middleware.rate_limit import RateLimitMiddleware
from opensoar.api.ai import router as ai_router
from opensoar.api.ai_dedup import router as ai_dedup_router
from opensoar.api.actions import router as actions_router
from opensoar.api.activities import router as activities_router
from opensoar.api.admin_retention import router as admin_retention_router
from opensoar.api.alerts import router as alerts_router
from opensoar.api.api_keys import router as api_keys_router
from opensoar.api.auth import router as auth_router
from opensoar.api.dashboard import router as dashboard_router
from opensoar.api.health import router as health_router
from opensoar.api.incidents import router as incidents_router
from opensoar.api.integrations import router as integrations_router
from opensoar.api.metrics import router as metrics_router
from opensoar.api.observables import router as observables_router
from opensoar.api.playbook_runs import router as runs_router
from opensoar.api.playbooks import router as playbooks_router
from opensoar.api.webhooks import router as webhooks_router
from opensoar.config import settings
from opensoar.core.registry import PlaybookRegistry
from opensoar.core.triggers import TriggerEngine
from opensoar.db import async_session
from opensoar.plugins import configure_local_auth, initialize_plugin_state, load_optional_plugins

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s [%(module)s:%(funcName)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
logger = logging.getLogger(__name__)

_registry: PlaybookRegistry | None = None
_trigger_engine: TriggerEngine | None = None


def get_registry() -> PlaybookRegistry:
    assert _registry is not None, "PlaybookRegistry not initialized"
    return _registry


def get_trigger_engine() -> TriggerEngine:
    assert _trigger_engine is not None, "TriggerEngine not initialized"
    return _trigger_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _registry, _trigger_engine

    logger.info("Starting OpenSOAR...")
    logger.info(f"Playbook directories: {settings.playbook_directories}")

    _registry = PlaybookRegistry(settings.playbook_directories)
    _registry.discover()
    _trigger_engine = TriggerEngine(_registry)

    async with async_session() as session:
        await _registry.sync_to_db(session)

    logger.info("OpenSOAR is ready.")
    yield
    logger.info("Shutting down OpenSOAR.")


app = FastAPI(
    title="OpenSOAR",
    description="Open-source, Python-native SOAR platform",
    version="0.1.0",
    lifespan=lifespan,
)
initialize_plugin_state(app)
configure_local_auth(
    app,
    login_enabled=settings.local_login_enabled,
    registration_enabled=settings.local_registration_enabled,
)

# ── Middleware ──────────────────────────────────────────────
# Order matters: Starlette wraps middleware in reverse registration order,
# so MetricsMiddleware (added last) is the outermost layer and records every
# request regardless of whether the rate limiter short-circuits with a 429.
app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
app.add_middleware(MetricsMiddleware)

# ── API routers (must be registered before static file catch-all) ────
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(activities_router, prefix="/api/v1")
app.include_router(playbooks_router, prefix="/api/v1")
app.include_router(runs_router, prefix="/api/v1")
app.include_router(incidents_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(observables_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(ai_dedup_router, prefix="/api/v1")
app.include_router(actions_router, prefix="/api/v1")
app.include_router(api_keys_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(admin_retention_router, prefix="/api/v1")

# ── Prometheus scrape endpoint (no /api/v1 prefix) ──────────────────
app.include_router(metrics_router)

# ── Plugin discovery ────────────────────────────────────────────────
load_optional_plugins(app)

# ── Static UI serving (production Docker build) ─────────────────────
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"

if STATIC_DIR.exists():
    logger.info(f"Serving static UI from {STATIC_DIR}")
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA fallback — serve index.html for all non-API routes."""
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
else:

    @app.get("/")
    async def root():
        return {
            "name": "OpenSOAR",
            "version": "0.1.0",
            "description": "Open-source, Python-native SOAR platform",
            "docs": "/docs",
        }
