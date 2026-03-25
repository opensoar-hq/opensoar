# Reddit Launch Drafts

Prepared for posting 1-2 days after the HN launch. Each post is tailored to its subreddit's audience and culture.

---

## 1. r/netsec — Technical Deep Dive

### Title

OpenSOAR: Open-source SOAR platform with Python async playbooks and built-in LLM triage (Apache 2.0)

### Post Body

We open-sourced a SOAR platform where playbooks are Python async functions instead of YAML or drag-and-drop workflows. Apache 2.0, self-hosted, AI features included for free.

**GitHub:** https://github.com/opensoar-hq/opensoar-core

#### The playbook engine

The core idea: security automation should be code you can test, lint, and version control. Playbooks use two decorators:

```python
from opensoar import playbook, action

@action(name="enrich_virustotal", timeout=30, retries=2, retry_backoff=2.0)
async def enrich_virustotal(iocs: dict) -> dict:
    """Each @action gets automatic timeout, retry with backoff, and execution tracking."""
    vt = VirusTotalIntegration({"api_key": settings.vt_api_key})
    await vt.connect()
    results = {}
    for ip in iocs.get("ips", []):
        raw = await vt.lookup_ip(ip)
        stats = raw["data"]["attributes"]["last_analysis_stats"]
        results[ip] = {"malicious": stats["malicious"], "suspicious": stats["suspicious"]}
    await vt.disconnect()
    return {"source": "virustotal", "results": results}

@playbook(trigger="webhook", conditions={"severity": ["high", "critical"]})
async def triage_high_severity(alert):
    # Parallel enrichment via asyncio.gather — implicit DAG, no workflow DSL
    vt_result, abuse_result = await asyncio.gather(
        enrich_virustotal(alert.iocs),
        enrich_abuseipdb(alert.source_ip),
    )
    risk = await calculate_risk(alert, vt_result, abuse_result)
    if risk["risk_score"] > 0.5:
        await notify_slack("#soc-critical", f"{alert.title} — risk {risk['risk_score']:.1f}")
```

Key design decisions:

- **No DSL or DAG definition language.** Parallelism = `asyncio.gather()`. Sequential = `await`. Standard Python control flow for branching.
- **`@action` decorator** tracks execution time, I/O, retries per action. Each action gets its own timeout and backoff config.
- **contextvars** for automatic run tracking — every action knows which playbook run it belongs to without threading state through function args.
- **PlaybookRegistry** auto-discovers `.py` files from configured directories, syncs to DB at startup.

#### AI integration (free, not upsell)

Three LLM providers supported — Anthropic (Claude), OpenAI, Ollama (local). The AI playbooks are real examples in the repo:

- **AI Phishing Triage** (`playbooks/examples/ai_phishing_triage.py`): Extracts IOCs, checks VT/AbuseIPDB in parallel, feeds enrichment + alert context to an LLM, gets structured JSON verdict (malicious/suspicious/benign with confidence score), auto-resolves benign or escalates.
- **AI Threat Hunt** (`playbooks/examples/ai_threat_hunt.py`): Collects all IOCs, hunts across all integrations in parallel (`asyncio.gather` over IPs, domains, hashes), LLM correlates findings into an analyst-ready report with MITRE ATT&CK context.
- **Playbook generation**: Describe what you want in English, get production Python.

The LLM calls use structured JSON output with fallback parsing — if the model doesn't return valid JSON, it degrades gracefully to a "manual review required" verdict instead of crashing the playbook.

#### Architecture

```
Webhooks/Elastic → Ingestion (normalize, extract IOCs, dedup)
    → Trigger Engine (match alert to playbook by severity/source/field conditions)
    → Celery Worker (async execution, retry, run tracking)
    → Actions (VT, AbuseIPDB, Slack, Email, isolate host, etc.)
```

Stack: Python 3.12, FastAPI, async SQLAlchemy + asyncpg, PostgreSQL 16, Redis 7, Celery, React 19 + Vite.

168+ tests, CI on GitHub Actions (lint + test + Docker multi-target build).

#### Quick start

```bash
git clone https://github.com/opensoar-hq/opensoar-core.git && cd opensoar-core
docker compose up -d
curl -X POST http://localhost:8000/api/v1/webhooks/alerts \
  -H "Content-Type: application/json" \
  -d '{"rule_name": "Brute Force Detected", "severity": "high", "source_ip": "203.0.113.42"}'
```

Looking for feedback on the playbook API design and the AI integration approach. If you've built SOAR automation before, curious what abstractions you'd want. Contributors welcome — especially for new SIEM normalizers and integration connectors.

---

## 2. r/cybersecurity — SOC Pain Points & TheHive Replacement

### Title

We built an open-source SOAR to replace TheHive + Cortex — Python playbooks, built-in AI, no per-action billing

### Post Body

TheHive was archived in December 2025. If you were one of the ~4,000 users, you know the scramble. The remaining options are either expensive (Splunk SOAR, XSOAR — $100K+/year with per-action billing), YAML-based, or GUI-first workflow builders.

We built **OpenSOAR** — an open-source SOAR platform (Apache 2.0) designed for the pain points we kept hitting:

**GitHub:** https://github.com/opensoar-hq/opensoar-core

#### What it solves

**1. "I just want to write Python, not fight a visual builder"**

Playbooks are async Python functions with decorators. Parallel enrichment is `asyncio.gather()`. Error handling is `try/except`. You can `pip install` anything. No sandbox, no DSL, no YAML.

```python
@playbook(trigger="webhook", conditions={"severity": ["high", "critical"]})
async def triage_high_severity(alert):
    vt, abuse = await asyncio.gather(
        lookup_virustotal(alert.iocs),
        lookup_abuseipdb(alert.source_ip),
    )
    if abuse.confidence_score > 80:
        await isolate_host(alert.hostname)
        await notify_slack("#soc-critical", f"{alert.title} — host isolated")
```

**2. "Cortex was a pain to maintain"**

TheHive needed Cortex (a separate Java service) with analyzers packaged as Docker containers. OpenSOAR has integrations built in — VirusTotal, AbuseIPDB, Slack, Email, Elastic. No Docker socket mounts, no analyzer versioning headaches.

| | TheHive 4 | OpenSOAR |
|---|---|---|
| Database | Cassandra + Elasticsearch + HDFS/MinIO | PostgreSQL |
| Analysis engine | Cortex (separate Java service) | Built-in |
| Containers needed | 5+ | 4 |
| Automation language | Cortex analyzers (Docker containers) | Python async |

**3. "AI shouldn't be a $50K add-on"**

Built-in LLM integration (Claude, OpenAI, or Ollama for fully local). It does:
- Alert summarization and triage recommendations with confidence scores
- Auto-resolve benign alerts (with audit trail)
- Threat hunt correlation across all your enrichment sources
- Playbook generation from plain English

This is free, not an enterprise upsell. We ship example AI playbooks you can run today.

**4. "We're an MSSP and need multi-tenant visibility"**

Partner field on every alert, per-partner MSSP dashboard stats, MTTR tracking per customer.

#### Migration from TheHive

We have a [migration guide](https://github.com/opensoar-hq/opensoar-core/blob/main/docs/migrating-from-thehive.md) with concept mapping, field mapping tables, and export/import scripts. Alerts, cases (→ incidents), observables, and activity all transfer.

Being honest about gaps: no case-level task checklists yet, no TLP/PAP as first-class fields (use tags), and 5 built-in integrations vs. Cortex's 100+ analyzer ecosystem. These are on the roadmap and contributions are welcome.

#### Get running

```bash
git clone https://github.com/opensoar-hq/opensoar-core.git && cd opensoar-core
docker compose up -d
# Open http://localhost:3000
```

Docker Compose brings up API, worker, PostgreSQL, Redis, and the React UI. Send a test alert via webhook and watch it flow through.

If you're running a SOC or doing IR, what's missing? What would make you actually switch?

---

## 3. r/selfhosted — Docker Deployment & Privacy

### Title

OpenSOAR — self-hosted security automation platform (SOAR) with AI. Docker Compose, Apache 2.0, no cloud dependency.

### Post Body

Built an open-source SOAR (Security Orchestration, Automation and Response) platform that runs entirely self-hosted. If you run security tools at home or for a small team and want to automate alert triage without paying for Splunk SOAR or sending your security data to a SaaS vendor, this might be for you.

**GitHub:** https://github.com/opensoar-hq/opensoar-core

#### What it does

It sits between your security tools (Elastic, Wazuh, or any webhook source) and your response actions. Alerts come in, get normalized and enriched automatically, and playbooks run to triage/respond. Think of it as "if this alert, then do these things" but with real Python code instead of Zaps or Node-RED flows.

#### Deployment

Single `docker compose up -d`. Four containers:

| Container | Purpose |
|---|---|
| **api** | FastAPI REST API |
| **worker** | Celery task worker (runs playbooks) |
| **postgres** | PostgreSQL 16 database |
| **redis** | Message broker + cache |

Plus an optional React UI container at `localhost:3000`. Total footprint is reasonable — Postgres and Redis are lightweight, the API is Python/uvicorn, the worker scales horizontally if you need it.

```bash
git clone https://github.com/opensoar-hq/opensoar-core.git && cd opensoar-core
docker compose up -d
# UI at http://localhost:3000, API at http://localhost:8000
```

The docker-compose also optionally includes Elasticsearch 8 + Kibana with a pre-configured webhook connector pointing back to OpenSOAR, so you can test the full SIEM-to-SOAR pipeline locally.

#### Privacy angle

- All data stays on your machine. No telemetry, no cloud calls unless you configure external integrations.
- AI features work with **Ollama** (fully local LLM) — no data leaves your network. Also supports Claude and OpenAI if you prefer cloud LLMs.
- Apache 2.0 license — use commercially, fork, embed, no restrictions.
- PostgreSQL for storage — easy to back up, restore, and inspect with standard tools.

#### For the homelabbers

If you're running Wazuh, Security Onion, or Elastic Security at home, OpenSOAR can receive their alerts via webhook, automatically extract IOCs (IPs, domains, hashes), and run playbooks. Example: auto-enrich suspicious IPs against VirusTotal and AbuseIPDB, get an AI-generated summary, and push a notification to your Slack/Discord.

The playbooks are Python files — if you can write a Python script, you can write a playbook:

```python
@playbook(trigger="webhook", conditions={"tags": "phishing"})
async def handle_phishing(alert):
    # Check URLs against VirusTotal
    vt = await lookup_virustotal(alert.iocs)
    # AI analyzes the alert + enrichment and gives a verdict
    verdict = await ai_analyze_phishing(alert, vt)
    if verdict["confidence"] > 0.85 and verdict["verdict"] == "benign":
        await auto_resolve(alert, reason=verdict["reasoning"])
    else:
        await notify_slack("#security", f"Phishing alert: {alert.title}")
```

#### What it's not

- Not a SIEM (doesn't collect logs — pair it with Elastic/Wazuh/Graylog)
- Not a firewall or IDS
- Not a SaaS product — fully self-hosted, no account needed

#### Stack

Python 3.12, FastAPI, PostgreSQL, Redis, Celery, React 19. 168+ tests, CI pipeline, Docker multi-stage builds.

Would love feedback from anyone running security tools in their homelab. What integrations would be most useful? Wazuh polling connector? MISP feed import? Discord notifications?
