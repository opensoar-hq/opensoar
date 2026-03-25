# Let Your AI Agent Set It Up

> Copy any prompt below and paste it into [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Cursor](https://cursor.sh), [ChatGPT](https://chatgpt.com), or your preferred AI coding assistant.

---

## Quick Start — Get OpenSOAR Running

```text
Clone the OpenSOAR repository and set it up on my machine:

1. git clone https://github.com/opensoar-hq/opensoar-core.git && cd opensoar-core
2. Run `docker compose up -d` to start all services (API, worker, Postgres, Redis, UI)
3. Wait for the API to be healthy: curl http://localhost:8000/api/v1/health
4. Send a test alert to verify ingestion works:
   curl -X POST http://localhost:8000/api/v1/webhooks/alerts \
     -H "Content-Type: application/json" \
     -d '{"rule_name": "Test Alert", "severity": "high", "source_ip": "203.0.113.42"}'
5. Open http://localhost:3000 in my browser and confirm the UI loads
6. Tell me the result of each step
```

---

## Dev Environment — Set Up for Contributing

```text
Set up a local development environment for OpenSOAR so I can contribute code:

1. Clone: git clone https://github.com/opensoar-hq/opensoar-core.git && cd opensoar-core
2. Create a Python 3.12 virtual environment: python3.12 -m venv .venv && source .venv/bin/activate
3. Install with dev dependencies: pip install -e ".[dev]"
4. Start Postgres and Redis: docker compose up -d postgres redis
5. Run database migrations: alembic upgrade head
6. Run the unit tests (no DB needed):
   pytest tests/test_normalize.py tests/test_decorators.py tests/test_triggers.py tests/test_scheduler.py -v
7. Run the full test suite:
   DATABASE_URL="postgresql+asyncpg://opensoar:opensoar@localhost:5432/opensoar_test" \
   JWT_SECRET="test-secret" API_KEY_SECRET="test-key" \
   pytest tests/ -v --tb=short
8. Start the API in dev mode: uvicorn opensoar.main:app --reload --port 8000
9. Confirm all tests pass and the API responds at http://localhost:8000/api/v1/health
```

---

## Write a New Playbook

```text
I want to create a new OpenSOAR playbook. Here's what it should do:

[Describe what the playbook should do, e.g. "When a high-severity alert comes in with a
suspicious IP, look it up on VirusTotal and AbuseIPDB in parallel, and if the confidence
score is above 80, send a Slack notification to #soc-alerts"]

Use the OpenSOAR playbook conventions:
- File goes in playbooks/examples/
- Use @playbook decorator with trigger="webhook" and appropriate conditions
- Use @action decorator for each step (with timeout and retries)
- Use asyncio.gather() for parallel enrichment
- Follow the patterns in the existing example playbooks
- Write tests first, then implement (TDD workflow from CLAUDE.md)
```

---

## Add a New Integration

```text
I want to add a new integration for [SERVICE NAME] to OpenSOAR.

1. Create a new directory: src/opensoar/integrations/[service_name]/
2. Create __init__.py and client.py
3. Subclass IntegrationBase from src/opensoar/integrations/base.py
4. Implement the required methods following the patterns in existing integrations
   (look at virustotal/ or abuseipdb/ for examples)
5. The IntegrationLoader will auto-discover it — no manual registration needed
6. Write tests in tests/ following the existing integration test patterns
7. Run the linter: ruff check src/ tests/
8. Run tests to confirm everything passes
```

---

## Add a New API Endpoint

```text
I want to add a new API endpoint to OpenSOAR:

[Describe the endpoint, e.g. "GET /api/v1/alerts/stats that returns alert count
grouped by severity for the last 24 hours"]

Follow OpenSOAR conventions:
- Create or edit a router in src/opensoar/api/
- Use Pydantic v2 schemas from src/opensoar/schemas/ for request/response
- Protect the endpoint with require_permission(Permission.X) from auth/rbac.py
- Use async database operations (AsyncSession)
- Write integration tests using the client fixture from conftest.py
- Follow TDD: write the test first, then implement
- Run ruff check and pytest before committing
```

---

## Connect to Elastic Security

```text
I have an Elastic Security instance and want to connect it to OpenSOAR for alert ingestion.

1. Make sure OpenSOAR is running (docker compose up -d)
2. Show me how to configure the Elastic integration in OpenSOAR's settings
3. Set up the webhook connector in Elastic to forward alerts to
   http://[opensoar-host]:8000/api/v1/webhooks/alerts
4. Send a test alert through and verify it appears in the OpenSOAR UI
5. Show me how to create a playbook that auto-triages Elastic alerts
```

---

## Deploy to Production

```text
Help me deploy OpenSOAR to production:

1. Review the docker-compose.yml and Dockerfile for production readiness
2. Set up proper environment variables:
   - Generate strong secrets for JWT_SECRET and API_KEY_SECRET
   - Configure DATABASE_URL for a production Postgres instance
   - Configure REDIS_URL for a production Redis instance
3. Build the production Docker images:
   docker build --target api -t opensoar-api .
   docker build --target worker -t opensoar-worker .
   docker build --target migrate -t opensoar-migrate .
   docker build --target ui -t opensoar-ui .
4. Run migrations: docker run --rm opensoar-migrate
5. Deploy the services (API, worker, UI) behind a reverse proxy with TLS
6. Verify health: curl https://[your-domain]/api/v1/health
7. Set up the first admin user and API key
```

---

## Troubleshooting

```text
I'm having an issue with my OpenSOAR setup: [describe the problem]

Debug it for me:
1. Check if all Docker containers are running: docker compose ps
2. Check API health: curl http://localhost:8000/api/v1/health
3. Check API logs: docker compose logs api --tail 50
4. Check worker logs: docker compose logs worker --tail 50
5. Check Postgres connectivity: docker compose exec postgres pg_isready
6. Check Redis connectivity: docker compose exec redis redis-cli ping
7. Tell me what's wrong and how to fix it
```

---

## Tips

- OpenSOAR uses **Python 3.12** with async everywhere — `asyncio`, `asyncpg`, `aiohttp`
- Playbooks are plain Python functions with decorators — no YAML, no DSL
- AI features (summarization, triage, playbook generation) are built-in and free
- The project follows TDD — always write tests first
- Lint with `ruff check src/ tests/` before committing
- Read `CLAUDE.md` for the full development guide and codebase conventions
