# Architecture

## Design Principles

1. **Python-native** — Playbook actions are Python functions. No DSL, no sandbox, no restricted stdlib. If you can `pip install` it, you can use it.
2. **SIEM-agnostic** — First-class support for Elastic Security and Wazuh. Pluggable adapter pattern for other SIEMs.
3. **Self-hosted first** — Docker Compose for small deployments, Kubernetes for scale. Cloud offering later.
4. **Developer experience over enterprise features** — Great DX attracts contributors. Enterprise features come from community scale.
5. **Modular and composable** — Each component (ingestion, orchestration, case management, enrichment) is independently deployable.

---

## High-Level Architecture

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
│                   Alert Normalization                                │
│                   (common schema)                                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Orchestration Engine                              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                   Playbook Runtime                           │    │
│  │                                                             │    │
│  │  - DAG-based execution (steps can run in parallel)          │    │
│  │  - Each action = Python function (async supported)          │    │
│  │  - Full Python environment (any pip package)                │    │
│  │  - Retry/backoff/timeout per action                         │    │
│  │  - Conditional branching, loops, error handling             │    │
│  │  - Execution sandboxing via containers (optional, for       │    │
│  │    untrusted community playbooks)                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Trigger      │  │  Scheduler   │  │  Event Correlation       │  │
│  │  Engine       │  │  (cron-based) │  │  (dedup, grouping)      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
┌──────────────────┐ ┌─────────────┐ ┌──────────────────┐
│  Case Management │ │  Enrichment │ │  Response Actions │
│                  │ │             │ │                    │
│  - Cases         │ │  - VT       │ │  - Isolate host   │
│  - Alerts        │ │  - AbuseIPDB│ │  - Block IP       │
│  - Tasks         │ │  - Shodan   │ │  - Disable user   │
│  - Timelines     │ │  - MISP     │ │  - Quarantine     │
│  - SLA tracking  │ │  - Custom   │ │  - Create ticket  │
│  - Collaboration │ │             │ │  - Notify          │
└──────────────────┘ └─────────────┘ └──────────────────┘
              │              │              │
              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Integration Layer                              │
│                                                                     │
│  Each integration = Python package with a standard interface        │
│  Community-contributed, versioned, tested                           │
│                                                                     │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐          │
│  │Elastic │ │ Wazuh  │ │ MISP   │ │ Jira   │ │ Slack  │  ...     │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘          │
└─────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Web UI                                      │
│                                                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐   │
│  │ Playbook Canvas │  │ Case Dashboard  │  │ Alert Queue         │   │
│  │ (visual editor) │  │ (case mgmt)     │  │ (triage view)       │   │
│  └────────────────┘  └────────────────┘  └─────────────────────┘   │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐   │
│  │ Analytics       │  │ Integration    │  │ Settings &           │   │
│  │ (dashboards)    │  │ Marketplace    │  │ Administration       │   │
│  └────────────────┘  └────────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Ingestion Layer

**Purpose**: Receive alerts from any SIEM and normalize them into a common schema.

**Design**:
- **Webhook receiver** — HTTP endpoint that accepts alert payloads from Elastic, Wazuh, or any tool that can POST JSON. This is the primary real-time integration path.
- **Polling connectors** — For SIEMs that don't support outbound webhooks, or for batch ingestion. Configurable polling intervals.
- **Message queue** — For high-volume deployments, alerts flow through a message queue (Redis Streams or NATS) for backpressure handling and reliability.
- **Alert normalization** — Incoming alerts are mapped to a common schema regardless of source. Each SIEM connector defines its own mapping.

**Key Elastic APIs to integrate**:
- Detection Rules API (`/api/detection_engine/rules`)
- Alerts API (`/api/detection_engine/signals`)
- Cases API (`/api/cases`)
- Webhook connector (outbound from Elastic to us)
- Elasticsearch query API (for ad-hoc investigation)
- Endpoint Management API (response actions)

**Key Wazuh APIs to integrate**:
- Alerts API
- Active Response API
- Agent management API
- Webhook/syslog forwarding

### 2. Orchestration Engine

**Purpose**: Execute playbooks — the core automation logic.

**Design**:
- **Playbooks are Python** — A playbook is a Python module. Each action is an async function decorated with `@action`. The runtime handles execution order, parallelism, retries, and error handling.
- **DAG execution** — Actions form a directed acyclic graph. Independent actions run in parallel. Dependencies are explicit.
- **Visual definition** — Playbooks can be created/edited in the visual Canvas UI and are stored as both visual metadata (for the UI) and executable Python (for the runtime). Changes in either are kept in sync.
- **Config-as-code** — Playbooks can also be defined entirely in code and version-controlled in Git. The UI renders them for visualization.

**Example playbook**:
```python
from opensoar import playbook, action, Alert, Case

@playbook(trigger="elastic.alert", conditions={"severity": "high"})
async def triage_high_severity(alert: Alert):

    # Enrich — runs in parallel
    vt_result, abuse_result = await asyncio.gather(
        enrich_virustotal(alert.iocs),
        enrich_abuseipdb(alert.source_ip),
    )

    # Score
    risk = calculate_risk(alert, vt_result, abuse_result)

    if risk > 0.8:
        # Create case and respond
        case = await Case.create(
            title=f"High-risk alert: {alert.rule_name}",
            severity="critical",
            alerts=[alert],
            enrichment={"virustotal": vt_result, "abuseipdb": abuse_result},
        )
        await isolate_host(alert.hostname)
        await notify_slack(channel="#soc", case=case)
    else:
        await alert.close(reason="auto-triaged", enrichment=vt_result)
```

### 3. Case Management

**Purpose**: Track incidents from detection through resolution. Replaces TheHive.

**Features**:
- Cases with alerts, observables, tasks, and timelines
- Task assignment and SLA tracking
- Collaboration (comments, attachments, @mentions)
- Observable tracking (IPs, domains, hashes, emails) with enrichment status
- Case templates for common incident types
- Metrics and reporting (MTTD, MTTR, case volume, analyst workload)

### 4. Integration Layer

**Purpose**: Connect to external tools and services.

**Design**:
- Each integration is a **Python package** that implements a standard interface
- Integrations are versioned and can be installed via pip
- Community integrations live in a separate repo (like Terraform providers)
- Standard interface: `connect()`, `health_check()`, `actions()`, `triggers()`

**Priority integrations** (Phase 1):
| Integration | Type | Purpose |
|------------|------|---------|
| Elastic Security | SIEM | Alert ingestion, case sync, response actions |
| Wazuh | SIEM/XDR | Alert ingestion, active response |
| VirusTotal | Enrichment | File/URL/IP reputation |
| AbuseIPDB | Enrichment | IP reputation |
| MISP | Threat Intel | IOC lookup and sharing |
| Slack | Notification | Alert/case notifications |
| Jira / ServiceNow | Ticketing | Ticket creation and sync |
| Email (SMTP/IMAP) | Notification + Ingestion | Alerts, phishing analysis |

### 5. Web UI

**Purpose**: Visual interface for playbook building, case management, alert triage, and administration.

**Tech stack** (proposed):
- **Frontend**: React + TypeScript
- **Playbook Canvas**: React Flow (node-based visual editor)
- **State management**: Zustand or TanStack Query
- **Design system**: Shadcn/ui (clean, accessible, customizable)

**Key views**:
- **Playbook Canvas** — Drag-and-drop playbook builder with live Python preview
- **Alert Queue** — Filterable, sortable triage view with bulk actions
- **Case Dashboard** — Case lifecycle management with timeline view
- **Analytics** — SOC metrics dashboards (MTTD, MTTR, alert volume, analyst workload)
- **Integration Marketplace** — Browse, install, and configure integrations
- **Admin** — User management, RBAC, audit logs, system health

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **API** | Python, FastAPI | Async-native, great DX, strong typing, massive ecosystem |
| **Task execution** | Celery + Redis or Temporal | Reliable async task execution with retries. Temporal for complex workflows if needed |
| **Database** | PostgreSQL | Reliable, feature-rich, JSON support for flexible schemas |
| **Cache / Queue** | Redis | Pub/sub, caching, rate limiting, lightweight queue |
| **Search** | PostgreSQL full-text (start), Elasticsearch (scale) | Start simple, add dedicated search engine when needed |
| **Frontend** | React, TypeScript, React Flow | Visual playbook builder, rich UI |
| **Deployment** | Docker Compose (dev/small), Kubernetes (production) | Progressive complexity |

---

## Deployment Models

### Small / Dev (Docker Compose)
```
docker compose up
```
Single-node deployment with all services. Good for teams up to ~10 analysts, ~1,000 alerts/day.

### Production (Kubernetes)
Horizontally scalable. Separate worker pools for different playbook priorities. HA PostgreSQL. Good for enterprises, MSSPs, and high-volume environments.

### Air-gapped
Container images available for offline installation. No external dependencies required at runtime (threat intel feeds can be loaded via file import).

---

## Security Considerations

- **RBAC** — Role-based access control for all resources (playbooks, cases, integrations, admin)
- **Audit logging** — All actions logged with user, timestamp, and details
- **Secrets management** — Integration credentials stored encrypted, never in playbook code. Support for external vaults (HashiCorp Vault, AWS Secrets Manager)
- **Playbook sandboxing** — Optional container-based isolation for untrusted community playbooks
- **API authentication** — API keys + OAuth2/OIDC for SSO integration
- **Network isolation** — Worker nodes can be deployed in isolated networks with limited egress
