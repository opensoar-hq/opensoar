# OpenSOAR Repository Structure

## GitHub Organization

**Organization**: [github.com/opensoar-hq](https://github.com/opensoar-hq)
**Domain**: opensoar.app

## Repositories

### opensoar-core (this repo) — Monorepo
The core platform — everything needed to run a fully functional SOAR, including the UI.

```
opensoar-core/
├── src/opensoar/          # Python backend
│   ├── api/               # FastAPI endpoints
│   ├── auth/              # JWT + API key auth
│   ├── core/              # Playbook engine, triggers, executor
│   ├── ingestion/         # Alert normalization, webhooks
│   ├── integrations/      # Built-in integrations (Elastic, VirusTotal, AbuseIPDB, Slack, Email)
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic schemas
│   └── worker/            # Celery tasks
├── ui/                    # React + Vite + Tailwind frontend (SOC dashboard)
├── migrations/            # Alembic migrations
├── playbooks/examples/    # Example playbooks
├── .github/workflows/     # CI: test + build Docker images
├── deploy/                # Production deploy config (docker-compose.yml, .env.example)
├── Dockerfile             # Multi-target: api, worker, migrate, ui
└── .dockerignore
```

**Docker images** (built by CI, pushed to GHCR):
- `ghcr.io/opensoar-hq/opensoar-core-api:latest`
- `ghcr.io/opensoar-hq/opensoar-core-worker:latest`
- `ghcr.io/opensoar-hq/opensoar-core-migrate:latest`
- `ghcr.io/opensoar-hq/opensoar-core-ui:latest`

**Why monorepo**: API and UI are tightly coupled — same Docker Compose, same PR for cross-cutting changes, simpler CI. No version coordination overhead.

**License**: Apache 2.0

---

### opensoar-sdk
Python SDK for building integrations and playbooks. This is what integration authors install.

```
opensoar-sdk/
├── src/opensoar_sdk/
│   ├── __init__.py        # Exports: @action, @playbook, Integration, Alert
│   ├── decorators.py      # @action (timeout, retries, backoff)
│   ├── base.py            # Integration ABC (connect, health_check, actions)
│   ├── models.py          # Alert, IOC, Enrichment data classes
│   ├── context.py         # RunContext (contextvars-based)
│   └── testing.py         # Test helpers (mock alert, mock run context)
├── tests/
└── pyproject.toml
```

**Why separate:**
- Integration authors only need `pip install opensoar-sdk` (lightweight, no FastAPI/SQLAlchemy deps)
- Stable API contract — core can change internals without breaking integrations
- Enables standalone integration testing

**License**: Apache 2.0

---

### opensoar-integrations
Community-contributed integration packs. Each integration is a self-contained directory.

```
opensoar-integrations/
├── integrations/
│   ├── crowdstrike/       # CrowdStrike Falcon (EDR)
│   ├── sentinelone/       # SentinelOne (EDR)
│   ├── jira/              # Jira (ITSM)
│   ├── pagerduty/         # PagerDuty (Alerting)
│   ├── misp/              # MISP (Threat Intel)
│   └── ...
├── templates/
│   └── integration-template/  # Cookiecutter template for new integrations
└── CONTRIBUTING.md
```

**Note**: Built-in integrations (Elastic, VirusTotal, AbuseIPDB, Slack, Email) ship with `opensoar-core`. This repo is for community/third-party packs that are developed and maintained independently.

**License**: Apache 2.0

---

### opensoar-www
Landing page at [opensoar.app](https://opensoar.app). Astro static site deployed via Cloudflare Pages.

**License**: Apache 2.0

---

## Repository Status

| Repo | Status | Artifact |
|------|--------|----------|
| opensoar-core | Active | `ghcr.io/opensoar-hq/opensoar-core-{api,worker,migrate,ui}` |
| opensoar-sdk | Active | `pypi.org/project/opensoar-sdk` |
| opensoar-integrations | Active | Community packs (5 connectors) |
| opensoar-www | Active | Cloudflare Pages |

The core platform ships with AI features (summarization, triage, playbook generation, correlation) included — all under Apache 2.0.
