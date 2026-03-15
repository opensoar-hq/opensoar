# Architecture

## Design Principles

1. **Python-native** — Playbook actions are Python functions. No DSL, no sandbox, no restricted stdlib. If you can `pip install` it, you can use it.
2. **SIEM-agnostic** — First-class support for Elastic Security and Wazuh. Pluggable adapter pattern for any SIEM.
3. **Self-hosted first** — Docker Compose for small deployments, Kubernetes for scale. Cloud offering later.
4. **Developer experience over enterprise features** — Great DX attracts contributors. Enterprise features come from community scale.
5. **Modular and composable** — Clean package boundaries enable splitting into separate repos when needed, not before.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Data Sources                               │
│  Elastic Security  │  Wazuh  │  Security Onion  │  Webhooks  │ API │
└────────┬───────────┴────┬────┴────────┬─────────┴─────┬──────┴─────┘
         │                │             │               │
         ▼                ▼             ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Ingestion Layer                                │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Webhook      │  │  Polling      │  │  Message Queue Consumer │  │
│  │  Receiver     │  │  Connectors   │  │  (for high-volume)      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │
│         └─────────────────┴──────────────────────┘                  │
│                            │                                        │
│              Alert Normalization + IOC Extraction                    │
│              (common schema, severity inference)                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Orchestration Engine                              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                   Playbook Runtime                           │    │
│  │                                                             │    │
│  │  - Python-native execution (async functions)                │    │
│  │  - @playbook and @action decorators                         │    │
│  │  - Parallel via asyncio.gather(), sequential via await      │    │
│  │  - Retry/backoff/timeout per action                         │    │
│  │  - contextvars for automatic run tracking                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Trigger      │  │  Scheduler   │  │  Playbook Registry       │  │
│  │  Engine       │  │  (APScheduler)│  │  (auto-discover .py)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
┌──────────────────┐ ┌─────────────┐ ┌──────────────────┐
│  Alert Mgmt      │ │  Enrichment │ │  Response Actions │
│                  │ │             │ │                    │
│  - Lifecycle     │ │  - VT       │ │  - Isolate host   │
│  - Determination │ │  - AbuseIPDB│ │  - Block IP       │
│  - Partner/MSSP  │ │  - Shodan   │ │  - Disable user   │
│  - Timeline      │ │  - MISP     │ │  - Create ticket  │
│  - IOCs          │ │  - Custom   │ │  - Notify (Slack)  │
└──────────────────┘ └─────────────┘ └──────────────────┘
              │              │              │
              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Integration Layer                              │
│                                                                     │
│  Each integration = Python module with standard interface           │
│  Built-in: Elastic, VT, AbuseIPDB, Slack, Email                   │
│  Community: via opensoar-integrations repo (future)                 │
│                                                                     │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐          │
│  │Elastic │ │  VT    │ │AbuseIP │ │ Slack  │ │ Email  │  ...     │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘          │
└─────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Web UI (React 19)                           │
│                                                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐   │
│  │ Dashboard       │  │ Alert Detail    │  │ Alert Queue         │   │
│  │ (IR-focused)    │  │ (triage view)   │  │ (bulk ops)          │   │
│  └────────────────┘  └────────────────┘  └─────────────────────┘   │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐   │
│  │ Playbook Runs   │  │ Settings       │  │ Login / Auth         │   │
│  │ (execution log)  │  │ (keys, config)  │  │ (JWT-based)         │   │
│  └────────────────┘  └────────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Ingestion Layer

**Purpose**: Receive alerts from any source and normalize them into a common schema.

**Implemented:**
- **Webhook receiver** (`POST /api/v1/webhooks/alerts`) — Accepts arbitrary JSON, normalizes automatically
- **Alert normalization** — Extracts title, severity, IPs, hostname, tags, partner from any payload format
- **Severity inference** — When no explicit severity, infers from event context (process names, auth failures, etc.)
- **IOC extraction** — Walks the payload tree to extract IPs, domains, hashes, URLs
- **Partner extraction** — Looks for `partner`, `tenant`, `customer`, `organization` fields

**Planned:**
- Elasticsearch polling connector (scheduled ingestion)
- Wazuh webhook + polling
- Message queue consumer for high-volume deployments (Redis Streams / NATS)

### 2. Orchestration Engine

**Purpose**: Execute playbooks — the core automation logic.

**Implemented:**
- **`@playbook` decorator** — Self-registers at import time, defines trigger conditions
- **`@action` decorator** — Wraps functions with timeout, retry, backoff metadata; tracks execution via contextvars
- **PlaybookRegistry** — Discovers playbooks by importing `.py` files from configured directories, syncs to DB
- **PlaybookExecutor** — Creates run record, sets contextvars, executes async function, records action results
- **TriggerEngine** — Matches alerts to playbooks by evaluating field conditions (severity thresholds, source matching)
- **Scheduler** — APScheduler for cron-based triggers

**Key design decision**: Implicit DAG via Python async. `asyncio.gather()` = parallelism, `await` = sequential. No DAG definition language.

### 3. Alert Management

**Purpose**: Full alert lifecycle from ingestion to resolution.

**Implemented:**
- Alert CRUD with filtering (severity, status, source, partner, determination)
- Lifecycle: `new` → `in_progress` → `resolved`
- Determination field: `unknown`, `malicious`, `suspicious`, `benign` (required for resolution)
- Partner field for MSSP tenant attribution
- Claim/assign/reassign workflow
- Duplicate detection and counting
- Activity timeline (unified comments + system events)
- Comment editing with edit history

### 4. Integration Layer

**Purpose**: Connect to external tools and services.

**Implemented:**
- `IntegrationBase` ABC — `connect()`, `health_check()`, `get_actions()`
- Elastic Security connector (alert normalization)
- VirusTotal (hash/IP/domain/URL lookup)
- AbuseIPDB (IP reputation)
- Slack (channel notifications)
- Email (SMTP)

**Future (opensoar-sdk):**
- Standalone SDK package for integration authors
- Integration manifest format (YAML)
- Dynamic loading from configured directories
- Community integration repository

### 5. Worker Layer

**Purpose**: Async playbook execution with reliability.

**Implemented:**
- Celery with Redis broker
- `execute_playbook_task(playbook_name, alert_id)` task
- Automatic retry on transient failures
- Run status tracking (pending → running → success/failed)
- Action result recording with timing and I/O data

### 6. API Layer

**Purpose**: REST API for all operations.

**Implemented:**
- FastAPI with auto-generated OpenAPI spec
- JWT authentication (login, token refresh)
- API key authentication (for integrations/webhooks)
- Endpoints: alerts, playbooks, runs, actions, activities, dashboard, integrations, settings
- Pydantic v2 request/response validation

### 7. Web UI

**Purpose**: Analyst-facing interface optimized for triage workflows.

**Implemented:**
- React 19 + TypeScript + Vite + Tailwind CSS v4
- Custom component library (Card, Dialog, Drawer, Toast, Table, Tabs, Sidebar, etc.)
- framer-motion animations throughout
- TanStack Query for data fetching
- Pages: Dashboard, Alerts List, Alert Detail, Playbooks, Runs, Run Detail, Settings, Login
- Dark theme (SOC-optimized)

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **API** | Python 3.12, FastAPI | Async-native, great DX, strong typing |
| **ORM** | SQLAlchemy 2.0 (async) + asyncpg | Async ORM, PostgreSQL-native |
| **Migrations** | Alembic | Industry standard for SQLAlchemy |
| **Task Queue** | Celery + Redis | Reliable async execution, horizontal scaling |
| **Database** | PostgreSQL 16 | Reliable, JSON support, full-text search |
| **Cache/Queue** | Redis 7 | Broker, caching, pub/sub |
| **Frontend** | React 19, TypeScript, Vite | Fast dev, strong typing |
| **Styling** | Tailwind CSS v4 | Utility-first, dark theme via CSS vars |
| **Animation** | framer-motion | Spring physics, AnimatePresence |
| **Data Fetching** | TanStack Query | Caching, optimistic updates, refetch |
| **Deployment** | Docker Compose | Single-command full stack |

---

## Multi-Repository Architecture (Planned)

As the project grows, components will split into separate repos under the `opensoar-hq` GitHub org:

| Repository | Purpose | License | When to split |
|------------|---------|---------|---------------|
| **opensoar-core** | Core platform + UI + AI features | Apache 2.0 | Active |
| **opensoar-sdk** | Python SDK for integration authors | Apache 2.0 | Active (PyPI v0.1.1) |
| **opensoar-integrations** | Community integration packs | Apache 2.0 | Active (5 connectors) |
| **opensoar-deploy** | Docker Compose deployment configs | Apache 2.0 | Active |
| **opensoar-www** | Marketing site (opensoar.app) | Apache 2.0 | Active |

See [Repository Structure](repository-structure.md) for full details.

---

## Deployment Models

### Development / Small Team (Docker Compose)
```bash
docker compose up -d
```
Single-node deployment with all services. Good for teams up to ~10 analysts, ~1,000 alerts/day.

### Production (Kubernetes) — Planned
Horizontally scalable. Separate worker pools for different playbook priorities. HA PostgreSQL. For enterprises, MSSPs, and high-volume environments.

### Air-gapped — Planned
Container images for offline installation. No external dependencies at runtime. Threat intel feeds loadable via file import.

---

## Security Considerations

- **JWT + API key auth** — JWT for UI sessions, API keys for integrations
- **Secrets management** — Integration credentials stored encrypted (Vault/AWS SM planned)
- **Audit trail** — Activity timeline records all analyst actions
- **Input validation** — Pydantic v2 on all API boundaries
- **RBAC** — Planned for Enterprise edition
- **SSO** — SAML/OIDC planned for Enterprise edition
