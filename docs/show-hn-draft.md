# Show HN Draft

## Title

**Show HN: OpenSOAR – Open-source SOAR with Python-native playbooks and AI**

## Post Body

Hi HN,

OpenSOAR is an open-source security orchestration and automated response (SOAR) platform. It lets SOC analysts and IR teams write security automation in plain Python — async functions, not YAML configs or drag-and-drop workflows. It's Apache 2.0, self-hosted, and the AI features are free.

GitHub: https://github.com/opensoar-hq/opensoar-core

**Why we built it:** TheHive, the most popular open-source incident response platform, was archived in December 2025. The remaining options are either proprietary (Splunk SOAR, Palo Alto XSOAR — $100K+/year), YAML-based (Tracecat), or GUI-first (Shuffle). We wanted something where a Python-literate analyst could write a playbook in 20 lines of actual code, not fight a visual builder or learn a DSL.

**What makes it different:**

- **Python-native playbooks** — `@playbook` and `@action` decorators, `asyncio.gather()` for parallel enrichment, standard try/except for error handling. Your playbooks are just Python files you can test, lint, and version control.
- **AI built-in and free** — LLM-powered triage recommendations, alert summarization, playbook generation, and auto-resolve. Works with Claude, OpenAI, or Ollama (local). Not a paid add-on.
- **No per-action billing** — commercial SOAR platforms charge per action or per automation run. OpenSOAR doesn't.
- **Batteries included** — webhook ingestion with automatic normalization (Elastic, generic JSON), IOC extraction, trigger engine, case management, RBAC, dark-themed React UI.

**Quick start:**

```bash
git clone https://github.com/opensoar-hq/opensoar-core.git && cd opensoar-core
docker compose up -d
# Open http://localhost:3000
```

**Example playbook:**

```python
@playbook(trigger="webhook", conditions={"severity": ["high", "critical"]})
async def triage_high_severity(alert: Alert):
    vt, abuse = await asyncio.gather(
        lookup_virustotal(alert.iocs),
        lookup_abuseipdb(alert.source_ip),
    )
    if abuse.confidence_score > 80:
        await isolate_host(alert.hostname)
        await notify_slack("#soc-critical", f"{alert.title} — host isolated")
```

**Stack:** Python 3.12, FastAPI, async SQLAlchemy, PostgreSQL, Redis, Celery, React 19, Vite

**What we're looking for:** Feedback on the architecture, the playbook API design, and the AI integration approach. If you run a SOC or do IR work, we'd love to hear what's missing. Contributors welcome — especially for new SIEM normalizers and response tool integrations.

---

## TL;DR First Comment (post immediately after submission)

Hey, creator here. Quick context:

I built OpenSOAR because I got tired of writing YAML to automate security workflows. The pitch is simple: your playbooks are Python async functions. You get `asyncio.gather()` for parallel enrichment, standard error handling, and you can pip install anything.

A few things that might come up:

- **"How is this different from Tracecat?"** — Tracecat uses YAML workflow definitions. OpenSOAR playbooks are pure Python — no DSL, no intermediate config. If you can write a FastAPI endpoint, you can write an OpenSOAR playbook.
- **"Why not just use n8n/Temporal/Prefect?"** — Those are general-purpose workflow engines. OpenSOAR is purpose-built for security: alert normalization, IOC extraction, severity-based triggers, case management, and MITRE ATT&CK context are built in.
- **"What about TheHive?"** — TheHive was the go-to OSS incident response tool but it was archived in late 2025. OpenSOAR fills that gap with a more automation-focused approach.
- **AI features** — The LLM integration supports Claude, OpenAI, and Ollama. It does alert summarization, triage suggestions, and can generate playbook drafts. It's free, not an upsell.

Happy to answer questions about the architecture, deployment, or anything else.
