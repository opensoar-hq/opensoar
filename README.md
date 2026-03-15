<p align="center">
  <img src="https://raw.githubusercontent.com/opensoar-hq/opensoar-www/main/public/logo.svg" width="64" height="62" alt="OpenSOAR">
</p>

<h1 align="center">OpenSOAR</h1>
<p align="center"><strong>Open-source, Python-native Security Orchestration, Automation, and Response (SOAR) platform.</strong></p>

OpenSOAR is the orchestration and automation layer for the modern SOC. It sits between your SIEM (Elastic, Wazuh, Splunk) and your response tools, letting you write automation logic in plain Python — no sandboxes, no per-action billing, no vendor lock-in.

Built for IR analysts and MSSPs. Dark-themed, fast, opinionated.

---

## Features

**Alert Management**
- Webhook ingestion with automatic normalization (Elastic, Wazuh, generic JSON)
- Alert lifecycle: `new` → `in_progress` → `resolved`
- Determination tracking (malicious, suspicious, benign)
- IOC extraction (IPs, domains, hashes, URLs)
- Deduplication and severity inference
- Partner/tenant field for MSSP multi-tenancy

**Playbook Engine**
- Python-native — playbooks are async Python functions, not YAML or drag-and-drop
- `@playbook` and `@action` decorators with automatic tracking
- Parallel execution via `asyncio.gather()`, sequential via `await`
- Timeout, retry, and backoff per action
- Trigger engine (severity, source, field matching)
- Celery-based async execution with horizontal scaling

**Integrations**
- Elastic Security (alerts, polling)
- VirusTotal (hash/IP/domain/URL lookup)
- AbuseIPDB (IP reputation)
- Slack (notifications)
- Email (SMTP)
- Extensible via Python SDK

**Dashboard & UI**
- React 19 + TypeScript + Tailwind CSS v4
- IR analyst-focused dashboard (priority queue, MTTR, unassigned alerts)
- Per-partner stats for MSSP billing
- Alert detail with triage, IOCs, timeline, playbook runs
- Activity timeline with comments and edit history
- Dark theme optimized for SOC environments

**Auth & API**
- JWT authentication with analyst management
- API key auth for integrations
- Full REST API (OpenAPI auto-generated)

---

## Quick Start

```bash
# Clone and start
git clone https://github.com/opensoar-hq/opensoar-core.git
cd opensoar-core
docker compose up -d

# Send a test alert
curl -X POST http://localhost:8000/api/v1/webhooks/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "Brute Force Detected",
    "severity": "high",
    "source_ip": "203.0.113.42",
    "hostname": "web-prod-01",
    "tags": ["authentication", "brute-force"]
  }'

# Open the UI
open http://localhost:3000
```

---

## Architecture

```
Elastic / Wazuh / Webhooks
         │
         ▼
  ┌──────────────┐
  │  Ingestion   │  Normalize → Extract IOCs → Deduplicate
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  Trigger     │  Match alert to playbook conditions
  │  Engine      │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  Celery      │  Async playbook execution
  │  Worker      │  @action tracking, retries, timeouts
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  Actions     │  Enrich (VT, AbuseIPDB) → Respond (isolate, block)
  │              │  → Notify (Slack, email) → Update (tickets, cases)
  └──────────────┘
```

**Stack**: Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL, Redis, Celery, React 19, Vite

---

## Example Playbook

```python
from opensoar import playbook, action, Alert
import asyncio

@playbook(trigger="webhook", conditions={"severity": ["high", "critical"]})
async def triage_high_severity(alert: Alert):
    # Enrich in parallel
    vt_result, abuse_result = await asyncio.gather(
        lookup_virustotal(alert.iocs),
        lookup_abuseipdb(alert.source_ip),
    )

    if abuse_result.confidence_score > 80:
        await isolate_host(alert.hostname)
        await notify_slack(
            channel="#soc-critical",
            message=f"🚨 {alert.title} — host isolated, VT: {vt_result.positives}/{vt_result.total}"
        )
    else:
        await alert.update(determination="benign", status="resolved")
```

No DSL. No YAML. Just Python.

---

## Project Structure

```
opensoar/
├── src/opensoar/
│   ├── api/            # FastAPI endpoints (alerts, playbooks, runs, dashboard)
│   ├── auth/           # JWT + API key authentication
│   ├── core/           # Playbook engine, triggers, executor, registry
│   ├── ingestion/      # Alert normalization, webhook processing
│   ├── integrations/   # Elastic, VirusTotal, AbuseIPDB, Slack, Email
│   ├── models/         # SQLAlchemy models
│   ├── schemas/        # Pydantic v2 request/response schemas
│   └── worker/         # Celery tasks
├── ui/                 # React frontend
├── migrations/         # Alembic database migrations
├── playbooks/          # Example playbooks
├── docker-compose.yml  # Full stack: API + worker + PostgreSQL + Redis
└── Dockerfile
```

---

## Documentation

- [Architecture](docs/architecture.md) — System design, component breakdown, deployment models
- [Design Decisions](docs/design-decisions.md) — UX and architectural rationale
- [Business Model](docs/business-model.md) — Open-core strategy, pricing, go-to-market
- [Repository Structure](docs/repository-structure.md) — Multi-repo plan (SDK, integrations, enterprise, AI)
- [Roadmap](docs/roadmap.md) — What's built, what's next
- [Market Research](docs/market-research.md) — Market size, demand signals, target users
- [Competitive Landscape](docs/competitive-landscape.md) — How we compare

---

## Roadmap

| Phase | Status | Focus |
|-------|--------|-------|
| Core Platform | ✅ Done | Alert management, playbook engine, API, UI |
| Quality + Hardening | ✅ Done | 119 tests, CI pipeline, webhook auth, rate limiting, health checks |
| SDK + Integrations | ✅ Done | SDK on PyPI, 5 integration packs implemented (30 methods) |
| Case Management | ✅ Done | Incidents, observables, correlation, enrichment tracking |
| Case Management | Planned | Incidents, correlation, collaboration |
| AI Features | Planned | Auto-triage, NL playbooks, alert correlation |
| Enterprise | Planned | RBAC, SSO, audit, multi-tenancy |
| Cloud | Planned | SaaS at opensoar.app |

---

## Contributing

OpenSOAR is in early development. If you're interested in contributing — integrations, playbooks, frontend, documentation — open an issue or reach out.

---

## License

Apache 2.0 — Use it commercially, fork it, embed it. No restrictions.
