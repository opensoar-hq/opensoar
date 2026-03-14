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
├── Dockerfile             # Multi-target: api, worker, migrate
└── .dockerignore
```

**Docker images** (built by CI, pushed to GHCR):
- `ghcr.io/opensoar-hq/opensoar-core-api:latest`
- `ghcr.io/opensoar-hq/opensoar-core-worker:latest`
- `ghcr.io/opensoar-hq/opensoar-core-migrate:latest`

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

### opensoar-deploy
Deployment configurations — Docker Compose, environment templates.

```
opensoar-deploy/
├── docker-compose.yml      # Production: pulls images from GHCR
├── docker-compose.dev.yml  # Dev: mounts source, hot reload
├── .env.example
└── README.md
```

**License**: Apache 2.0

---

### opensoar-www
Landing page at [opensoar.app](https://opensoar.app). Astro static site deployed via Cloudflare Pages.

**License**: Apache 2.0

---

### opensoar-ee (future, private)
Enterprise features. Loaded as plugins into the core platform.

- RBAC, SSO/SAML, multi-tenancy, audit logging, SLA engine, reporting

**License**: Business Source License (BSL 1.1) — converts to Apache 2.0 after 3 years

---

### opensoar-ai (future, private)
AI features for the Cloud/Enterprise tier.

- Auto-classification, semantic correlation, NL summaries, playbook generation, threat hunting

**License**: Proprietary

---

### opensoar-cloud (future, private)
SaaS infrastructure, billing, onboarding.

**License**: Proprietary

---

## Repository Status

| Repo | Status | Artifact |
|------|--------|----------|
| opensoar-core | Active | `ghcr.io/opensoar-hq/opensoar-core-{api,worker,migrate}` |
| opensoar-sdk | Active | `pypi.org/project/opensoar-sdk` |
| opensoar-integrations | Active (in development) | Community packs |
| opensoar-deploy | Active | Config only |
| opensoar-www | Active | Cloudflare Pages |
| opensoar-ui | Archived | Merged into opensoar-core monorepo |
| opensoar-ee | Future | Plugin package |
| opensoar-ai | Future | Plugin package |
| opensoar-cloud | Future | Private infra |
