# OpenSOAR Core — Development Guidelines

## Development Workflow

### Test-Driven Implementation
When implementing new features or fixing bugs, always follow this order:

1. **Write tests first** — define expected behavior before writing implementation
2. **Run tests** — confirm they fail for the right reasons
3. **Implement** — write the minimal code to make tests pass
4. **Lint** — run `ruff check src/ tests/` and fix all errors
5. **Run full suite** — `pytest tests/ -v --tb=short` must pass (87+ tests)
6. **Commit** — include both tests and implementation in the same commit
7. **Push + verify CI** — watch `gh run watch` to confirm all jobs pass

### Running Tests Locally

```bash
# Unit tests (no DB needed)
.venv/bin/pytest tests/test_normalize.py tests/test_decorators.py tests/test_triggers.py -v

# Full suite (needs Postgres)
DATABASE_URL="postgresql+asyncpg://opensoar:opensoar@localhost:5432/opensoar_test" \
JWT_SECRET="test-secret" API_KEY_SECRET="test-key" \
.venv/bin/pytest tests/ -v --tb=short

# Lint
.venv/bin/ruff check src/ tests/
```

### CI Pipeline
- `test` job: Postgres 16 + Redis 7, ruff lint, pytest
- `build` job: Docker multi-target (api, worker, migrate, ui) → GHCR
- Build only runs on push to main, gated on test passing

## Architecture

- **Backend**: Python 3.12, FastAPI, async SQLAlchemy, Celery, PostgreSQL, Redis
- **Frontend**: React 19, TypeScript, Vite 8, Tailwind CSS v4 (in `ui/`)
- **Monorepo**: API + UI in one repo, one Dockerfile with 4 targets

## Key Patterns

- All DB operations are async (`AsyncSession`)
- Playbooks are Python async functions with `@playbook` and `@action` decorators
- Alert normalization handles multiple payload formats (generic, Elastic, Wazuh)
- IOC extraction walks payloads recursively (depth-limited to 10)
- Deduplication by `source + source_id`
- Resolving an alert requires a determination (not "unknown")

## Test Fixtures

- `client` — HTTPX AsyncClient with mocked trigger engine and DB override
- `session` — direct AsyncSession for unit tests
- `registered_analyst` / `sample_alert_via_api` — create data via API for integration tests
- `analyst` / `sample_alert` — create data directly in DB for unit tests
- All use `asyncio_default_test_loop_scope = "session"` for proper async fixture sharing
