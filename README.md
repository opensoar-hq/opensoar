<p align="center">
  <img src="https://raw.githubusercontent.com/opensoar-hq/opensoar-www/main/public/logo.svg" width="64" height="62" alt="OpenSOAR">
</p>

<h1 align="center">OpenSOAR</h1>
<p align="center"><strong>Open-source SOAR platform. Write security automation in Python, not YAML.</strong></p>

<p align="center">
  <a href="https://github.com/opensoar-hq/opensoar-core/actions/workflows/build.yml"><img src="https://github.com/opensoar-hq/opensoar-core/actions/workflows/build.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License"></a>
  <a href="https://github.com/opensoar-hq/opensoar-core/stargazers"><img src="https://img.shields.io/github/stars/opensoar-hq/opensoar-core?style=social" alt="GitHub Stars"></a>
  <a href="https://ghcr.io/opensoar-hq/opensoar-core"><img src="https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker" alt="Docker"></a>
</p>

---

OpenSOAR is the orchestration and automation layer for the modern SOC. It sits between your SIEM (Elastic, Splunk) and your response tools, letting you write automation logic in plain Python — no sandboxes, no per-action billing, no vendor lock-in.

Built for IR analysts and MSSPs. Dark-themed, fast, opinionated.

**Get running in 30 seconds:**

```bash
git clone https://github.com/opensoar-hq/opensoar-core.git && cd opensoar-core && docker compose up -d
```

Then open [http://localhost:3000](http://localhost:3000).

Docs: [docs.opensoar.app](https://docs.opensoar.app)

---

## Why OpenSOAR?

### vs. Open-Source Alternatives

| | **OpenSOAR** | Shuffle | Tracecat | StackStorm |
|---|---|---|---|---|
| GitHub stars | New | ~2,200 | ~3,500 | ~6,000 |
| License | Apache 2.0 | AGPL-3.0 | AGPL-3.0 | Apache 2.0 |
| Automation | Python (async) | Visual/JSON workflows | YAML workflows | YAML + Python |
| Built-in AI | Yes (free) | No | Yes | No |
| Integrations | 5 built-in | 1,000+ (app library) | Growing | 160+ packs |
| Playbook style | Code-first | Drag-and-drop | YAML definitions | YAML rules + Python |
| Backed by | Community | Community | YC W24 | Linux Foundation (minimal activity) |

**Honest take:** Shuffle and StackStorm have far more integrations today. But their approaches — drag-and-drop JSON or YAML rule files — hit a ceiling fast when you need conditional logic, parallel enrichment, or custom response flows. OpenSOAR gives you native Python with `async`/`await`, which means anything you can write in Python, you can automate. No DSL translation layer, no sandbox limitations.

Tracecat is the closest competitor in philosophy (YC-backed, developer-focused) but uses YAML workflows and AGPL licensing, which restricts how you can embed and redistribute it.

**Also worth knowing:**
- **TheHive** — formerly the go-to open-source SOAR, now archived. StrangeBee pivoted to commercial-only licensing. If you're migrating off TheHive, OpenSOAR is a natural landing spot.
- **DFIR-IRIS** — excellent open-source incident response platform (LGPL), but focused on case management and forensics, not orchestration/automation. Complementary to OpenSOAR, not a replacement.

### vs. Commercial Platforms

| | **OpenSOAR** | Tines | Palo Alto XSOAR |
|---|---|---|---|
| License | Apache 2.0 | Proprietary | Proprietary |
| Per-action billing | No | Yes | Yes |
| Self-hosted | Yes | No | On-prem option |
| Built-in AI | Yes (free) | Paid add-on | Paid add-on |
| Playbook style | Code-first | Drag-and-drop | Mixed (YAML + Python) |
| Best for | Python-literate SOC teams | No-code teams | Enterprises with Palo Alto stack |

---

## Features

- [x] **Webhook ingestion** — automatic normalization (Elastic, generic JSON), IOC extraction, deduplication
- [x] **Python-native playbooks** — `@playbook` and `@action` decorators, `asyncio.gather()` for parallelism, retry/timeout per action
- [x] **Trigger engine** — match alerts to playbooks by severity, source, or field conditions
- [x] **Integrations** — Elastic Security, VirusTotal, AbuseIPDB, Slack, Email, extensible via Python SDK
- [x] **Case management** — incidents, observables, correlation suggestions
- [x] **AI-powered** — LLM summarization, triage recommendations, playbook generation, auto-resolve, correlation (Claude, OpenAI, Ollama)
- [x] **Dashboard & UI** — React 19, dark theme, priority queue, MTTR, per-partner MSSP stats
- [x] **Auth & RBAC** — JWT + API keys, 3 roles, 15 permissions
- [x] **Celery workers** — async execution with horizontal scaling
- [x] **Plugin architecture** — load optional enterprise features if installed

---

## Documentation

Canonical documentation lives at **[docs.opensoar.app](https://docs.opensoar.app)**.

Start there for:

- installation and getting started
- playbook authoring and loading
- deployment and operations
- API usage
- troubleshooting
- engineering and architecture references

---

## Roadmap

| Phase | Status | Focus |
|-------|--------|-------|
| Core Platform | ✅ | Alert management, playbook engine, API, React UI |
| Quality + Ops | ✅ | 168 tests, CI pipeline, webhook auth, rate limiting |
| SDK + Integrations | ✅ | SDK on PyPI, 5 community packs (30 API methods) |
| Case Management | ✅ | Incidents, observables, correlation suggestions |
| AI Features | ✅ | LLM summarization, triage, playbook gen, auto-resolve |
| Enterprise | ✅ | RBAC (3 roles, 15 permissions), plugin architecture |
| Cloud | 📋 | SaaS at opensoar.app |

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Areas where help is most needed:
- **Integrations** — new SIEM normalizers, response tool connectors
- **Playbooks** — community playbook packs for common scenarios
- **Frontend** — dashboard improvements, new visualizations
- **Documentation** — guides, tutorials, deployment recipes

---

## License

Apache 2.0 — Use it commercially, fork it, embed it. No restrictions.
