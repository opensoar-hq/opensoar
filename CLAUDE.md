# OpenSOAR Core — AI Development Guide

> This file is read by Claude Code, Cursor, Copilot, and other AI coding agents when working on this project.

## Project Overview

OpenSOAR is an open-source SOAR (Security Orchestration, Automation & Response) platform. It replaces YAML-based automation with plain Python — `@playbook` and `@action` decorators, async execution, and a full REST API. Licensed Apache 2.0.

## Architecture

- **Monorepo**: API + UI + AI in one repo. All Apache 2.0.
- **Backend**: Python 3.12, FastAPI, async SQLAlchemy 2.0, Celery 5, PostgreSQL 16, Redis 7
- **Frontend**: React 19, TypeScript 5.9, Vite 8, Tailwind CSS v4 (in `ui/`)
- **Dockerfile**: 4 build targets — `api`, `worker`, `migrate`, `ui`
- **AI**: Built into core (free and open-source). Supports Claude, OpenAI, Ollama.
- **Plugin system**: Core uses a plugin architecture to load optional enterprise features if installed.

## Project Structure

```
src/opensoar/
├── api/            # FastAPI routers (alerts, playbooks, runs, incidents, dashboard, ai, webhooks, auth, settings)
├── auth/           # JWT tokens, API key hashing, RBAC (Analyst/Admin/Viewer, 15 permissions)
├── core/           # Playbook engine: decorators.py, executor.py, triggers.py, scheduler.py, registry.py
├── ingestion/      # Alert normalization (severity inference, IOC extraction), webhook processing
├── integrations/   # Elastic, VirusTotal, AbuseIPDB, Slack, Email + loader.py (dynamic discovery)
├── models/         # SQLAlchemy async models (alert, playbook, incident, observable, analyst, etc.)
├── schemas/        # Pydantic v2 request/response schemas
├── worker/         # Celery tasks (execute_playbook_task)
├── middleware/     # Rate limiter (token bucket)
├── config.py       # pydantic-settings (env vars)
├── db.py           # Async SQLAlchemy engine + session factory
└── main.py         # FastAPI app, startup hooks
ui/src/
├── pages/          # Dashboard, Alerts, Incidents, Runs, Playbooks, Settings, Login
├── components/     # Reusable Tailwind components (Button, Table, Card, Dialog, etc.)
├── context/        # AuthContext (JWT management, role-based UI)
└── api.ts          # Axios wrapper for /api/v1 endpoints
playbooks/examples/ # Sample playbooks (triage, enrichment, AI phishing, threat hunt)
migrations/         # Alembic database migrations
scripts/            # install.sh, seed.py, elastic_poller.py
tests/              # 168+ tests (unit + integration)
```

## Open-Source Rules

- **Never reference private repos** in public code, docs, or READMEs.
- **Never mention pricing, licensing strategy, or business model** in public repos.
- **AI features are free and open-source** — this is the viral differentiator. Never move them behind a paywall.
- **Enterprise features** (SSO, multi-tenancy, SLA, compliance) are loaded via an optional plugin package if installed.

## How to Run Locally

```bash
# Full stack with Docker (recommended)
docker compose up -d
# API at http://localhost:8000, UI at http://localhost:3000

# Dev setup (without Docker)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d postgres redis  # still need Postgres + Redis
alembic upgrade head
uvicorn opensoar.main:app --reload --port 8000
```

## Development Workflow (TDD)

When implementing new features or fixing bugs, always follow this order:

1. **Write tests first** — define expected behavior before writing implementation
2. **Run tests** — confirm they fail for the right reasons
3. **Implement** — write the minimal code to make tests pass
4. **Lint** — `ruff check src/ tests/` must pass with zero errors
5. **Run full suite** — `pytest tests/ -v --tb=short` (168+ tests)
6. **Commit** — tests + implementation together in one commit
7. **Push + verify CI** — `gh run watch` to confirm all 5 jobs pass (test, api, worker, migrate, ui)

## Running Tests Locally

```bash
# Unit tests only (no DB needed)
.venv/bin/pytest tests/test_normalize.py tests/test_decorators.py tests/test_triggers.py tests/test_scheduler.py -v

# Full suite (needs Postgres + Redis running)
DATABASE_URL="postgresql+asyncpg://opensoar:opensoar@localhost:5432/opensoar_test" \
JWT_SECRET="test-secret" API_KEY_SECRET="test-key" \
.venv/bin/pytest tests/ -v --tb=short
```

## CI Pipeline

- **test**: Postgres 16 + Redis 7, ruff lint, pytest
- **build**: Docker multi-target (api, worker, migrate, ui) → GHCR
- Build only runs on push to main, gated on test passing

## Key Patterns

### Playbook & Action Decorators (`src/opensoar/core/decorators.py`)
```python
@action(name="lookup_ip", timeout=30, retries=2, backoff=5)
async def lookup_ip(ip: str):
    ...

@playbook(trigger="webhook", conditions={"severity": ["high", "critical"]})
async def my_playbook(alert_data):
    results = await asyncio.gather(lookup_ip(...), lookup_hash(...))
    return {"verdict": "malicious"}
```
Actions track execution context via `contextvars` for automatic result recording.

### Trigger Engine (`src/opensoar/core/triggers.py`)
Matches alerts to playbooks by evaluating source and field conditions against the alert payload. Each trigger has `source_filter` and `conditions` (field → allowed values).

### Integration Adapter Pattern (`src/opensoar/integrations/base.py`)
All integrations implement `IntegrationBase` with standard interface methods. `IntegrationLoader` discovers built-in integrations + any external packages.

### Alert Normalization (`src/opensoar/ingestion/normalize.py`)
Extracts title, severity, source, IPs, domains, hashes, and URLs from any payload format. Handles Elastic Security payloads, generic JSON, and raw strings. `extract_field()` treats `None` values as "not found" (falls through to default).

### RBAC (`src/opensoar/auth/rbac.py`)
Three roles: Analyst, Admin, Viewer. 15 permissions. Use `require_permission(Permission.X)` as a FastAPI dependency.

### Async Database
All DB operations use `AsyncSession`. Engine configured in `db.py` with `asyncpg` driver.

### Rate Limiter (`src/opensoar/middleware/rate_limit.py`)
Token bucket algorithm, module-level `_buckets` dict, reset via `reset_rate_limiter()` in test conftest.

### LLM Client (`src/opensoar/api/ai.py`)
Verified against official API docs — Anthropic Messages API, OpenAI Chat Completions, Ollama /api/generate. Supports summarization, triage recommendations, playbook generation, and auto-resolve.

## Common Tasks

### Add a New Integration
1. Create `src/opensoar/integrations/myservice/` with `__init__.py` and `client.py`
2. Subclass `IntegrationBase` from `src/opensoar/integrations/base.py`
3. Implement required methods (connect, execute, etc.)
4. The `IntegrationLoader` auto-discovers integrations — no manual registration needed
5. Add tests in `tests/test_integrations.py`

### Add a New Playbook
1. Create a file in `playbooks/examples/` (or any configured playbook directory)
2. Use `@playbook(trigger="webhook", conditions={...})` decorator
3. Define actions with `@action(name="...", timeout=30, retries=2)`
4. Use `asyncio.gather()` for parallel actions
5. The `PlaybookRegistry` auto-discovers playbooks on startup

### Add a New API Endpoint
1. Create or edit a router in `src/opensoar/api/`
2. Use `require_permission(Permission.X)` for RBAC
3. Use Pydantic v2 schemas from `src/opensoar/schemas/` for request/response validation
4. Register the router in `src/opensoar/main.py` if it's a new file
5. Add integration tests using the `client` fixture

### Add a Database Migration
1. Modify models in `src/opensoar/models/`
2. Run `alembic revision --autogenerate -m "description"`
3. Review the generated migration in `migrations/versions/`
4. Apply with `alembic upgrade head`

## Test Fixtures (in `tests/conftest.py`)

- `client` — HTTPX AsyncClient with mocked trigger engine, rate limiter reset, DB override
- `registered_analyst` / `registered_admin` — create users via API for integration tests
- `sample_alert_via_api` — create alert via webhook for integration tests
- `session` — direct AsyncSession for unit tests
- `db_session_factory` — session factory for tests that need direct DB access alongside client

## Common Gotchas

- TypeScript build (`tsc -b`) is stricter than `tsc --noEmit` — unused imports fail the Docker UI build
- `extract_field()` in `normalize.py` treats `None` values as "not found" (falls through to default)
- Elastic payloads have `source` as a dict — normalizer checks `isinstance(raw_source, str)`
- `asyncpg` needs all tests on the same event loop — use `asyncio_default_test_loop_scope = "session"`
- Rate limiter accumulates across tests in session scope — conftest resets buckets before each client fixture
- Alembic migrations must use async-compatible operations

## Docs Maintenance

- **Single source of truth**: Don't maintain the same info in multiple .md files
- Core README has the roadmap table — keep it high-level (one line per phase)
- Detailed architecture in `docs/architecture.md`
- Business strategy docs stay in private repos only
- When updating state, grep for stale references across all public repos before committing
