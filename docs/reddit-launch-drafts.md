# Reddit Launch Drafts

Prepared for posting 1-2 days after the HN launch. Each post is tailored to its subreddit's audience and culture.

---

## 1. r/netsec — Technical Deep Dive

### Title

TheHive was archived in December 2025. We built an open-source SOAR successor in Python (Apache 2.0, async playbooks, built-in LLM triage)

### Post Body

TheHive was the de facto open-source SOAR platform for years — 3,900 stars, hundreds of SOC teams running it. Then StrangeBee archived the open-source repos in December 2025 and moved everything behind a commercial license. 821 issues frozen. No migration path.

The community fragmented. Some went to Shuffle, some to DFIR-IRIS, some started evaluating Tracecat. None of them are a drop-in replacement. We built **OpenSOAR** to fill that gap — a Python-native SOAR platform that's Apache 2.0 and will stay that way.

**GitHub:** https://github.com/opensoar-hq/opensoar-core

#### Why another SOAR?

Here's the honest landscape of what's available right now:

| | **OpenSOAR** | **Shuffle** | **Tracecat** | **DFIR-IRIS** | **StackStorm** |
|---|---|---|---|---|---|
| **Stars** | New | ~2,200 | ~3,500 | ~2,000 | ~6,400 |
| **License** | Apache 2.0 | AGPLv3 | AGPL (was Apache) | LGPL-3.0 | Apache 2.0 |
| **Automation** | Python async | Visual/YAML | No-code + YAML | Python modules | YAML + Python |
| **Case management** | Yes (incidents, observables) | No | Limited | Yes (core focus) | No |
| **Built-in AI** | Yes (free) | No | Yes (paid tier) | No | No |
| **Integrations** | 5 built-in | 200+ | 100+ | Modules | 200+ packs |
| **Status** | Active | Active, 1-10 person team | Beta after 2 years, $2M raised | Active | Life support (acquisition carousel) |

**We're honest about the gaps.** Shuffle and StackStorm have 200+ integrations. We have 5 (VirusTotal, AbuseIPDB, Slack, Email, Elastic). The trade-off: our integrations are Python classes you can read, test, and extend — not black-box Docker containers or YAML configs. The `IntegrationBase` adapter pattern means adding a new one is ~50 lines of Python.

StackStorm has 6,400 stars but has been through Brocade → Broadcom → Extreme Networks → Linux Foundation. Development has effectively stalled. Tracecat raised $2M from YC but is still in beta after two years and switched from Apache 2.0 to AGPL — the same license bait-and-switch pattern that killed community trust in TheHive.

#### The playbook engine

The core bet: security automation should be testable Python, not YAML or drag-and-drop.

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
    # Parallel enrichment — implicit DAG, no workflow DSL
    vt_result, abuse_result = await asyncio.gather(
        enrich_virustotal(alert.iocs),
        enrich_abuseipdb(alert.source_ip),
    )
    risk = await calculate_risk(alert, vt_result, abuse_result)
    if risk["risk_score"] > 0.5:
        await notify_slack("#soc-critical", f"{alert.title} — risk {risk['risk_score']:.1f}")
```

Key design decisions:

- **No DSL.** Parallelism = `asyncio.gather()`. Sequential = `await`. Branching = `if/else`.
- **`@action` decorator** tracks execution time, I/O, retries per action. Each action gets its own timeout and backoff config.
- **contextvars** for automatic run tracking — every action knows which playbook run it belongs to without threading state through function args.
- **PlaybookRegistry** auto-discovers `.py` files from configured directories, syncs to DB at startup.

#### AI integration (free, not upsell)

Three LLM providers — Anthropic (Claude), OpenAI, Ollama (local). The AI playbooks are real examples in the repo:

- **AI Phishing Triage**: Extracts IOCs, checks VT/AbuseIPDB in parallel, feeds enrichment + alert context to an LLM, gets structured JSON verdict (malicious/suspicious/benign with confidence score), auto-resolves benign or escalates.
- **AI Threat Hunt**: Collects all IOCs, hunts across all integrations in parallel, LLM correlates findings into an analyst-ready report with MITRE ATT&CK context.
- **Playbook generation**: Describe what you want in English, get production Python.

This is Apache 2.0 — not a "free tier" that gates the useful features. Tracecat's AI features require their paid cloud tier. Ours ship in the open-source repo.

#### Architecture

```
Webhooks/Elastic → Ingestion (normalize, extract IOCs, dedup)
    → Trigger Engine (match alert to playbook by severity/source/field conditions)
    → Celery Worker (async execution, retry, run tracking)
    → Actions (VT, AbuseIPDB, Slack, Email, isolate host, etc.)
```

Stack: Python 3.12, FastAPI, async SQLAlchemy + asyncpg, PostgreSQL 16, Redis 7, Celery, React 19 + Vite. 168+ tests, CI on GitHub Actions.

#### Quick start

```bash
git clone https://github.com/opensoar-hq/opensoar-core.git && cd opensoar-core
docker compose up -d
curl -X POST http://localhost:8000/api/v1/webhooks/alerts \
  -H "Content-Type: application/json" \
  -d '{"rule_name": "Brute Force Detected", "severity": "high", "source_ip": "203.0.113.42"}'
```

Looking for feedback on the playbook API design and the Python-native approach vs. visual builders. If you've migrated off TheHive, what are you using now and what's missing? Contributors welcome — especially for new integration connectors and SIEM normalizers.

---

## 2. r/cybersecurity — Community Fragmentation & TheHive Replacement

### Title

TheHive is dead. The open-source SOAR community is fragmented. We're building the replacement.

### Post Body

TheHive was archived in December 2025. StrangeBee moved everything to a commercial-only model — TheHive 5 requires a license after a 14-day trial, then goes read-only. The open-source repos are frozen with 821 unresolved issues.

If you were one of the ~4,000 users, you already know the scramble. The problem isn't that there are no alternatives — it's that **no single tool replaced what TheHive did**.

Here's what happened to the community:

- **Shuffle** → Good for workflow automation, but no case management. ~2,200 stars (not 15K as sometimes reported). AGPLv3.
- **DFIR-IRIS** → Closest to TheHive's case management, but focused on digital forensics. Less automation.
- **Tracecat** → YC-backed ($2M), but still in beta after 2 years. Switched from Apache 2.0 to AGPL.
- **StackStorm** → 6,400 stars but effectively on life support after being passed through Brocade → Broadcom → Extreme Networks → Linux Foundation.
- **Cortex XSOAR / Splunk SOAR** → $100K+/year with per-action billing. Not an option for most teams.

**No one tool covers alert triage + case management + playbook automation + observable enrichment** the way TheHive + Cortex did. The community fragmented.

We built **OpenSOAR** to be that single platform again.

**GitHub:** https://github.com/opensoar-hq/opensoar-core

#### What it covers

**1. "I just want to write Python, not fight a visual builder"**

Playbooks are async Python functions with decorators. Parallel enrichment is `asyncio.gather()`. Error handling is `try/except`. You can `pip install` anything.

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

TheHive needed Cortex (a separate Java service) with analyzers as Docker containers. OpenSOAR has integrations built in — no Docker socket mounts, no analyzer versioning headaches.

| | TheHive 4 | OpenSOAR |
|---|---|---|
| Database | Cassandra + Elasticsearch + HDFS/MinIO | PostgreSQL |
| Analysis engine | Cortex (separate Java service) | Built-in |
| Containers needed | 5+ | 4 |
| Automation language | Cortex analyzers (Docker containers) | Python async |

**3. "AI shouldn't be a $50K add-on"**

Built-in LLM integration (Claude, OpenAI, or Ollama for fully local). Alert summarization, triage recommendations, auto-resolve benign alerts, threat hunt correlation, playbook generation from English. This is free and open-source — not an enterprise upsell.

**4. Where we're honest about gaps**

We have 5 built-in integrations (VirusTotal, AbuseIPDB, Slack, Email, Elastic). TheHive's Cortex ecosystem had 100+. Shuffle has 200+. We don't have MISP integration yet, no case templates, no bulk observable analysis, no TLP/PAP as first-class fields. These are on the roadmap and contributions are welcome — the integration framework is designed for this (`IntegrationBase` adapter pattern, auto-discovery).

The trade-off: fewer integrations, but each one is a Python class you can read, test, and debug. Adding a new integration is ~50 lines of code.

#### Migration from TheHive

We have a [migration guide](https://github.com/opensoar-hq/opensoar-core/blob/main/docs/migrating-from-thehive.md) with concept mapping, field mapping tables, and export/import scripts. Alerts, cases (→ incidents), observables, and activity all transfer.

| TheHive Concept | OpenSOAR Equivalent |
|---|---|
| Alert | Alert (with auto-normalization + IOC extraction) |
| Case | Incident |
| Observable | Observable |
| Cortex Analyzer | Integration (Python class) |
| Cortex Responder | Action (`@action` decorator) |
| Case Template | Playbook (`@playbook` decorator) |

#### Get running

```bash
git clone https://github.com/opensoar-hq/opensoar-core.git && cd opensoar-core
docker compose up -d
# Open http://localhost:3000
```

Docker Compose brings up API, worker, PostgreSQL, Redis, and the React UI. Send a test alert via webhook and watch it flow through.

If you migrated off TheHive, what did you switch to? What's still missing? What would make you switch again?

---

## 3. r/selfhosted — License Anger & Privacy-First Deployment

### Title

OpenSOAR — self-hosted SOAR platform after TheHive pulled the open-source rug. Apache 2.0 forever, local AI with Ollama, single docker compose up.

### Post Body

TheHive was the go-to open-source security platform for years. Then StrangeBee archived the repos and moved to commercial-only licensing. 14-day trial, then read-only mode. The classic open-source bait-and-switch.

It's the same pattern we keep seeing: build community goodwill with open source, get traction, pull the rug. Elastic did it. HashiCorp did it. Now TheHive. Tracecat started Apache 2.0, already switched to AGPL.

We built **OpenSOAR** and made a deliberate choice: **Apache 2.0, forever.** No CLA that lets us relicense later. No "open core" where the useful features are behind a paywall. The AI features — the part that every other vendor charges extra for — ship free in the open-source repo.

**GitHub:** https://github.com/opensoar-hq/opensoar-core

#### One command to run

```bash
git clone https://github.com/opensoar-hq/opensoar-core.git && cd opensoar-core
docker compose up -d
# UI at http://localhost:3000, API at http://localhost:8000
```

Four containers, reasonable footprint:

| Container | Purpose |
|---|---|
| **api** | FastAPI REST API |
| **worker** | Celery task worker (runs playbooks) |
| **postgres** | PostgreSQL 16 database |
| **redis** | Message broker + cache |

Plus an optional React UI container. The docker-compose also optionally includes Elasticsearch 8 + Kibana with a pre-configured webhook connector, so you can test the full SIEM-to-SOAR pipeline locally.

#### Nothing leaves your network

- **All data stays local.** No telemetry, no cloud calls unless you configure external integrations.
- **AI with Ollama** — fully local LLM, no data leaves your machine. Also supports Claude and OpenAI if you prefer cloud LLMs, but Ollama is a first-class citizen.
- **PostgreSQL** for storage — `pg_dump` to back up, standard tools to inspect. No Cassandra/Elasticsearch/MinIO stack like TheHive required.
- **Apache 2.0** — use commercially, fork, embed, no restrictions. No AGPL, no BSL, no SSPL.

#### For homelabbers running security tools

If you're running Wazuh, Security Onion, or Elastic Security at home, OpenSOAR receives their alerts via webhook, automatically extracts IOCs (IPs, domains, hashes, URLs), and runs playbooks. Example: suspicious IP comes in → auto-enrich against VirusTotal and AbuseIPDB → AI generates a summary → notification to Slack/Discord.

The playbooks are Python files:

```python
@playbook(trigger="webhook", conditions={"tags": "phishing"})
async def handle_phishing(alert):
    vt = await lookup_virustotal(alert.iocs)
    verdict = await ai_analyze_phishing(alert, vt)
    if verdict["confidence"] > 0.85 and verdict["verdict"] == "benign":
        await auto_resolve(alert, reason=verdict["reasoning"])
    else:
        await notify_slack("#security", f"Phishing alert: {alert.title}")
```

If you can write a Python script, you can write a playbook. No YAML, no visual builder, no proprietary DSL.

#### What it's not

- Not a SIEM (pair it with Elastic/Wazuh/Graylog)
- Not a firewall or IDS
- Not a SaaS — fully self-hosted, no account needed, no phone-home

#### Being honest

We have 5 built-in integrations today (VirusTotal, AbuseIPDB, Slack, Email, Elastic). Shuffle has 200+. We're early. The integration framework is designed for community contributions — each integration is a Python class with a standard interface, auto-discovered at startup. But if you need 50 integrations on day one, we're not there yet.

What we do have that others don't: Python-native playbooks (not YAML), built-in AI that's actually free, and a license that won't change on you.

#### Stack

Python 3.12, FastAPI, PostgreSQL, Redis, Celery, React 19. 168+ tests, CI pipeline, Docker multi-stage builds.

What integrations would be most useful for your homelab? Wazuh polling? MISP feeds? Discord notifications? Let us know.
