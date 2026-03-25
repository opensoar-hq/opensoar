# OpenSOAR Core — Development Guidelines

## Architecture

- **Monorepo**: API + UI + AI in one repo. All Apache 2.0.
- **Backend**: Python 3.12, FastAPI, async SQLAlchemy, Celery, PostgreSQL, Redis
- **Frontend**: React 19, TypeScript, Vite 8, Tailwind CSS v4 (in `ui/`)
- **Dockerfile**: 4 targets — api, worker, migrate, ui
- **AI**: Built into core (not a separate paid package). Supports Claude, OpenAI, Ollama.
- **Plugin system**: Core uses a plugin architecture to load optional enterprise features if installed.

## Open-Source Rules

- **Never reference private repos** in public code, docs, or READMEs.
- **Never mention pricing, licensing strategy, or business model** in public repos.
- **AI features are free and open-source** — this is the viral differentiator. Never move them behind a paywall.
- **Enterprise features** (SSO, multi-tenancy, SLA, compliance) are loaded via an optional plugin package if installed.

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
# Unit tests only (no DB)
.venv/bin/pytest tests/test_normalize.py tests/test_decorators.py tests/test_triggers.py tests/test_scheduler.py -v

# Full suite (needs Postgres)
DATABASE_URL="postgresql+asyncpg://opensoar:opensoar@localhost:5432/opensoar_test" \
JWT_SECRET="test-secret" API_KEY_SECRET="test-key" \
.venv/bin/pytest tests/ -v --tb=short
```

## CI Pipeline

- **test**: Postgres 16 + Redis 7, ruff lint, pytest
- **build**: Docker multi-target (api, worker, migrate, ui) → GHCR
- Build only runs on push to main, gated on test passing

## Key Patterns

- All DB operations are async (`AsyncSession`)
- `asyncio_default_test_loop_scope = "session"` in pytest config — required for async fixtures sharing
- Rate limiter uses module-level `_buckets` dict, reset via `reset_rate_limiter()` in test conftest
- LLM client: verified against official API docs (Anthropic Messages API, OpenAI Chat Completions, Ollama /api/generate)
- RBAC: `require_permission(Permission.X)` FastAPI dependency for endpoint protection
- Integration loader: `IntegrationLoader` discovers built-in + external connectors

## Docs Maintenance

- **Single source of truth**: Don't maintain the same info in multiple .md files
- Core README has the roadmap table — keep it high-level (one line per phase)
- Detailed architecture in `docs/architecture.md`
- Business strategy docs stay in private repos only
- When updating state, grep for stale references across all public repos before committing

## Test Fixtures

- `client` — HTTPX AsyncClient with mocked trigger engine, rate limiter reset, DB override
- `registered_analyst` / `registered_admin` — create users via API for integration tests
- `sample_alert_via_api` — create alert via webhook for integration tests
- `session` — direct AsyncSession for unit tests
- `db_session_factory` — session factory for tests that need direct DB access alongside client

## Common Gotchas

- TypeScript build (`tsc -b`) is stricter than `tsc --noEmit` — unused imports fail the Docker UI build
- `extract_field()` in normalize.py treats `None` values as "not found" (falls through to default)
- Elastic payloads have `source` as a dict — normalizer checks `isinstance(raw_source, str)`
- `asyncpg` needs all tests on the same event loop — use `asyncio_default_test_loop_scope = "session"`
- Rate limiter accumulates across tests in session scope — conftest resets buckets before each client fixture
