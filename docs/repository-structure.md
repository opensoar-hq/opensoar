# OpenSOAR Repository Structure

## GitHub Organization

**Organization**: github.com/opensoar-app (mirrors opensoar.app domain)

## Repositories

### opensoar (this repo)
The core platform — everything needed to run a fully functional SOAR.

```
opensoar/
├── src/opensoar/          # Python backend
│   ├── api/               # FastAPI endpoints
│   ├── auth/              # JWT + API key auth
│   ├── core/              # Playbook engine, triggers, executor
│   ├── ingestion/         # Alert normalization, webhooks
│   ├── integrations/      # Built-in integrations
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic schemas
│   └── worker/            # Celery tasks
├── ui/                    # React frontend
├── migrations/            # Alembic migrations
├── playbooks/examples/    # Example playbooks
├── docker-compose.yml
└── Dockerfile
```

**License**: Apache 2.0

---

### opensoar-sdk (future)
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

### opensoar-integrations (future)
Community-contributed integration packs. Each integration is a self-contained directory.

```
opensoar-integrations/
├── integrations/
│   ├── crowdstrike/
│   │   ├── manifest.yaml      # Name, version, author, actions, config schema
│   │   ├── connector.py       # CrowdStrike(Integration) class
│   │   ├── actions.py         # @action functions
│   │   ├── normalize.py       # Alert normalization (if it's a source)
│   │   ├── tests/
│   │   └── README.md
│   ├── sentinelone/
│   ├── microsoft-defender/
│   ├── splunk/
│   ├── jira/
│   ├── pagerduty/
│   ├── shodan/
│   ├── greynoise/
│   └── ...
├── templates/
│   └── integration-template/  # Cookiecutter template for new integrations
└── CONTRIBUTING.md
```

**Integration manifest format:**
```yaml
name: crowdstrike
display_name: CrowdStrike Falcon
version: 1.0.0
author: OpenSOAR Community
description: CrowdStrike Falcon integration for host isolation, detection lookup, and IOC management
category: edr
min_sdk_version: "0.1.0"

config:
  base_url:
    type: string
    required: true
    description: CrowdStrike API base URL
  client_id:
    type: string
    required: true
    secret: true
  client_secret:
    type: string
    required: true
    secret: true

actions:
  - name: isolate_host
    description: Isolate a host by hostname or device ID
    inputs: [hostname, device_id]
  - name: lookup_detection
    description: Look up a detection by ID
    inputs: [detection_id]
  - name: search_iocs
    description: Search IOCs in CrowdStrike Falcon
    inputs: [type, value]

triggers:
  - name: crowdstrike.detection
    description: New CrowdStrike detection
    type: webhook
```

**License**: Apache 2.0

---

### opensoar-ee (future, private)
Enterprise features. Loaded as plugins into the core platform.

```
opensoar-ee/
├── src/opensoar_ee/
│   ├── rbac/              # Fine-grained permissions
│   ├── tenancy/           # Multi-tenant isolation
│   ├── sso/               # SAML, OIDC providers
│   ├── audit/             # Immutable audit logging
│   ├── reporting/         # Scheduled reports, PDF generation
│   └── sla/               # SLA engine, breach detection
└── pyproject.toml
```

**License**: Business Source License (BSL 1.1) — converts to Apache 2.0 after 3 years

---

### opensoar-ai (future, private)
AI features for the Cloud/Enterprise tier.

```
opensoar-ai/
├── src/opensoar_ai/
│   ├── triage/            # Auto-classification (malicious/benign/suspicious)
│   ├── correlation/       # Semantic alert grouping
│   ├── summarization/     # Natural language alert/incident summaries
│   ├── playbook_gen/      # NL → Python playbook generation
│   ├── hunting/           # Threat hunting assistant
│   └── models/            # Model configs, prompts, evaluation
└── pyproject.toml
```

**License**: Proprietary

---

### opensoar-cloud (future, private)
SaaS infrastructure, billing, onboarding.

```
opensoar-cloud/
├── infra/                 # Terraform/Pulumi IaC
├── billing/               # Stripe integration, usage metering
├── onboarding/            # Tenant provisioning, setup wizard
├── proxy/                 # Multi-tenant routing
└── monitoring/            # SaaS health, per-tenant metrics
```

**License**: Proprietary

---

## When to Split

Don't split prematurely. Current priority:

| Repo | When to create | Trigger |
|------|---------------|---------|
| opensoar | Now (exists) | — |
| opensoar-sdk | When first external contributor wants to build an integration | Community need |
| opensoar-integrations | When we have 5+ integrations beyond the built-in set | Volume |
| opensoar-ee | When first enterprise customer needs RBAC/SSO | Revenue |
| opensoar-ai | When AI triage prototype is working | Product validation |
| opensoar-cloud | When SaaS beta launches | Go-to-market |

For now, keep everything in the main `opensoar` repo with clean package boundaries so splitting is a mechanical operation, not a refactor.
