# Migrating from TheHive to OpenSOAR

TheHive was archived in December 2025. If you're one of the 3,900+ users looking for a new home, OpenSOAR is a natural fit — open-source, Python-native, and built for the same SOC workflows you already know.

This guide maps TheHive concepts to OpenSOAR, walks through the migration process, and is honest about what's different.

---

## Concept Mapping

| TheHive | OpenSOAR | Notes |
|---------|----------|-------|
| **Alert** | **Alert** | Direct equivalent. Both support severity, status, tags, source tracking, and deduplication. |
| **Case** | **Incident** | TheHive "cases" map to OpenSOAR "incidents." Both track severity, status, assignment, and link to alerts. |
| **Observable / Artifact** | **Observable** | Both store IOC type + value. OpenSOAR adds enrichment status tracking and links to both alerts and incidents. |
| **Task** (within a case) | *(not yet available)* | TheHive had per-case task checklists (Waiting → InProgress → Completed). OpenSOAR doesn't have case-level tasks yet. Use incident descriptions or comments to track sub-tasks. |
| **Task Log** | **Activity / Comment** | Work logs map to OpenSOAR's activity timeline and comment system on alerts. |
| **Analyzer** (Cortex) | **Integration + Action** | Cortex analyzers (VirusTotal, AbuseIPDB, etc.) map to OpenSOAR's built-in integrations and manual actions. |
| **Responder** (Cortex) | **Playbook** | Cortex responders (block IP, send notification) map to OpenSOAR playbooks — but with full Python instead of a container. |
| **Case Template** | *(not yet available)* | TheHive's case templates (pre-filled severity, tasks, tags) don't have a direct equivalent. Playbook triggers can automate some of this. |
| **Custom Fields** | **Tags + raw_payload** | TheHive had typed custom fields (string/number/boolean/date). OpenSOAR uses tags for categorization and preserves the full raw payload as JSON. |
| **TLP / PAP** | *(not yet available)* | Traffic Light Protocol and Permissible Actions Protocol aren't tracked as first-class fields. Use tags (`tlp:amber`, `pap:green`) as a workaround. |
| **Organization** | **Partner (MSSP)** | TheHive's multi-org isolation maps loosely to OpenSOAR's partner field for MSSP multi-tenancy. |
| **Dashboard** | **Dashboard** | Both provide SOC metrics. OpenSOAR includes MTTR per partner, severity breakdowns, and priority queues. |
| **MISP Integration** | *(not yet available)* | TheHive had native MISP sync. OpenSOAR's integration system is extensible — a MISP connector can be built. |
| **Cortex** | **Built-in AI + Integrations** | OpenSOAR replaces Cortex with built-in AI (triage, correlation, summarization) and native integrations. No separate service to run. |

---

## What You Gain

Moving to OpenSOAR isn't just a lateral move. You get capabilities TheHive never had:

### AI-Powered SOC (Built-In, Free)
- **Alert Summarization** — LLM-generated plain-English summaries of any alert
- **AI Triage** — Automated severity and determination suggestions with confidence scores
- **Auto-Resolve** — Batch evaluation of alerts for automatic benign resolution
- **Correlation Analysis** — LLM-assisted grouping of related alerts into attack chains
- **Playbook Generation** — Describe what you want in English, get production Python code

### Python-Native Playbooks
TheHive required Cortex (a separate Java service) with analyzers packaged as Docker containers. OpenSOAR playbooks are plain Python with decorators:

```python
from opensoar import playbook, action, Alert

@playbook(trigger="webhook", conditions={"severity": ["high", "critical"]})
async def enrich_and_notify(alert: Alert):
    vt_result = await lookup_virustotal(alert.iocs)
    await send_slack_alert(alert, vt_result)

@action(name="virustotal.lookup", timeout=30, retries=2)
async def lookup_virustotal(iocs: list):
    # Full Python stdlib — no sandbox, no container overhead
    ...
```

No Docker socket mounts. No Cortex service. No analyzer versioning headaches.

### Simpler Architecture
| | TheHive 4 | OpenSOAR |
|---|---|---|
| **Database** | Cassandra + Elasticsearch + HDFS/MinIO | PostgreSQL |
| **Task queue** | — | Celery + Redis |
| **Analysis engine** | Cortex (separate Java service) | Built-in |
| **Containers needed** | 5+ (TheHive, Cassandra, ES, Cortex, MinIO) | 4 (API, worker, migrate, UI) |
| **Language** | Scala/Java | Python |

---

## What You Lose (Gaps to Know About)

We believe in being honest. Here's what TheHive had that OpenSOAR doesn't — yet:

| TheHive Feature | Status in OpenSOAR | Workaround |
|---|---|---|
| **Case-level tasks** (checklists within cases) | Not available | Track in incident description or use playbooks for automated steps |
| **Case templates** (pre-filled severity, tasks, tags) | Not available | Use playbook triggers to auto-enrich new incidents |
| **TLP / PAP fields** | Not first-class fields | Use tags: `tlp:amber`, `pap:green` |
| **Custom fields** (typed, per-case/alert) | Not available | Use tags or store in raw_payload JSON |
| **Case merging** | Not available | Manually link alerts to the same incident |
| **MISP integration** | Not built-in | Integration system is extensible — build a connector |
| **100+ Cortex analyzers** | 5 built-in integrations | VirusTotal, AbuseIPDB, Slack, Email, Elastic. More coming. Write your own with the integration base class. |
| **Observable sighting** | Not available | Use enrichment status and enrichment data |
| **File observables** (attachments) | Not available | Store file hashes as observables; reference files externally |
| **Resolution status** (TruePositive/FalsePositive) | **Available** as `determination` | Maps directly: `malicious`=TruePositive, `benign`=FalsePositive, `suspicious`≈Indeterminate |
| **Impact status** | Not available | Track in incident description |
| **Dashboard export/import** | Not available | Dashboard is API-driven (`GET /api/v1/dashboard/stats`) |
| **Graph-based data model** | Relational (PostgreSQL) | Simpler to query, back up, and maintain |

Many of these gaps are on the [roadmap](../README.md). Contributions welcome.

---

## Migration Steps

### Prerequisites

- A running TheHive instance (or access to its API/database backups)
- A running OpenSOAR instance ([deployment guide](../README.md))
- Python 3.10+ with `requests` installed
- API keys for both platforms

### Step 1: Export Data from TheHive

The cleanest way to export is via TheHive's REST API. If your instance is still running:

```bash
# Install the export helper
pip install requests

# Run the export script (see scripts/migrate_from_thehive.py)
python scripts/migrate_from_thehive.py export \
  --thehive-url https://thehive.example.com \
  --thehive-api-key YOUR_THEHIVE_API_KEY \
  --output-dir ./thehive-export
```

This exports:
- All alerts (with observables)
- All cases (with tasks, observables, and task logs)
- Case-alert links
- Users (for reference — not imported directly)

If your TheHive instance is offline, you'll need to work from database backups:
- **TheHive 3**: Export from Elasticsearch using `elasticdump`
- **TheHive 4/5**: Export from Cassandra using `cqlsh COPY` or Spark

### Step 2: Transform and Import to OpenSOAR

```bash
python scripts/migrate_from_thehive.py import \
  --opensoar-url http://localhost:8000 \
  --opensoar-api-key YOUR_OPENSOAR_API_KEY \
  --input-dir ./thehive-export
```

The import script handles:

1. **Alerts** — Maps TheHive alerts to OpenSOAR alerts:
   - `severity` 1-4 → `low`, `medium`, `high`, `critical`
   - `status` New/Updated → `new`, Ignored → `resolved` (determination: `benign`), Imported → `new`
   - `source` + `sourceRef` → `source` + `source_id`
   - `tags` → `tags`
   - `artifacts` → observables (created and linked)
   - Full original payload preserved in `raw_payload`

2. **Cases → Incidents** — Maps TheHive cases to OpenSOAR incidents:
   - `title`, `description`, `severity`, `tags` map directly
   - `status` Open → `open`, Resolved/Deleted → `closed`
   - Case-alert links preserved via incident-alert associations

3. **Observables** — Maps TheHive artifacts to OpenSOAR observables:
   - `dataType` → `type`
   - `data` → `value`
   - `tags` → `tags`
   - Cortex analyzer reports → `enrichments`

4. **Activity** — Task logs and case updates → OpenSOAR activity timeline

### Step 3: Verify the Migration

```bash
# Check counts match
curl -s http://localhost:8000/api/v1/dashboard/stats | python3 -m json.tool

# Spot-check a few alerts
curl -s http://localhost:8000/api/v1/alerts?limit=5 | python3 -m json.tool

# Verify observables were linked
curl -s http://localhost:8000/api/v1/observables?limit=5 | python3 -m json.tool
```

### Step 4: Reconnect Your Integrations

| TheHive Integration | OpenSOAR Equivalent |
|---|---|
| Elastic SIEM alerts → TheHive | Elastic webhook → OpenSOAR (`POST /api/v1/webhooks/alerts/elastic`) |
| Cortex VirusTotal analyzer | OpenSOAR VirusTotal integration (`POST /api/v1/integrations`) |
| Cortex AbuseIPDB analyzer | OpenSOAR AbuseIPDB integration |
| MISP feed → TheHive alerts | Write a polling playbook or build a MISP integration |
| Slack/Email responders | OpenSOAR Slack/Email integrations |
| Custom Cortex analyzers | Rewrite as OpenSOAR playbooks (Python, not Docker) |

### Step 5: Set Up Playbooks

Convert your Cortex analyzer + responder workflows into OpenSOAR playbooks:

**Before (TheHive + Cortex):**
1. Alert arrives → TheHive
2. Analyst runs VirusTotal analyzer on observable → Cortex → Docker container → result
3. If malicious, analyst runs "Block IP" responder → Cortex → Docker container → action

**After (OpenSOAR):**
```python
@playbook(trigger="webhook", conditions={"severity": ["high", "critical"]})
async def auto_enrich_and_respond(alert: Alert):
    # Step 1: Enrich IOCs (replaces Cortex analyzers)
    for ioc in alert.iocs:
        vt = await virustotal_lookup(ioc)
        abuse = await abuseipdb_check(ioc)

    # Step 2: AI triage (new — TheHive didn't have this)
    triage = await ai_triage(alert)

    # Step 3: Respond (replaces Cortex responders)
    if triage.determination == "malicious":
        await block_ip(alert.source_ip)
        await send_slack_alert(alert, channel="#soc-critical")
```

---

## Field Mapping Reference

### Alert Fields

| TheHive Field | OpenSOAR Field | Transform |
|---|---|---|
| `_id` | — | Not imported (new IDs generated) |
| `title` | `title` | Direct |
| `description` | `description` | Direct |
| `severity` (1-4) | `severity` (enum) | 1→low, 2→medium, 3→high, 4→critical |
| `status` | `status` | New/Updated→new, Ignored→resolved, Imported→new |
| `source` | `source` | Direct |
| `sourceRef` | `source_id` | Direct |
| `type` | `tags` | Added as tag: `thehive-type:{value}` |
| `tlp` (0-3) | `tags` | Added as tag: `tlp:{white\|green\|amber\|red}` |
| `pap` (0-3) | `tags` | Added as tag: `pap:{white\|green\|amber\|red}` |
| `tags` | `tags` | Direct |
| `date` | `created_at` | Direct |
| `customFields` | `raw_payload.custom_fields` | Preserved in raw payload |
| `artifacts` | observables | Created and linked to alert |
| `caseTemplate` | — | Not applicable |
| `follow` | — | Not applicable |

### Case → Incident Fields

| TheHive Field | OpenSOAR Field | Transform |
|---|---|---|
| `caseId` | — | Stored in tags: `thehive-case:{caseId}` |
| `title` | `title` | Direct |
| `description` | `description` | Direct |
| `severity` (1-4) | `severity` (enum) | Same as alerts |
| `status` | `status` | Open→open, Resolved/Deleted→closed |
| `owner` | `assigned_username` | Direct |
| `tags` | `tags` | Direct |
| `resolutionStatus` | — | Added to tags: `resolution:{value}` |
| `impactStatus` | — | Added to tags: `impact:{value}` |
| `summary` | `description` | Appended to description on closed incidents |
| `tlp` / `pap` | `tags` | Same as alerts |
| `metrics` | — | Preserved in raw data if needed |
| `customFields` | — | Not directly mapped |

### Observable Fields

| TheHive Field | OpenSOAR Field | Transform |
|---|---|---|
| `dataType` | `type` | Direct (ip, domain, hash, url, etc.) |
| `data` | `value` | Direct |
| `message` | `tags` | Added as context tag |
| `tlp` / `pap` | `tags` | Same as alerts |
| `ioc` | `tags` | If true, adds `ioc:true` tag |
| `sighted` | `tags` | If true, adds `sighted:true` tag |
| `tags` | `tags` | Direct |
| Cortex reports | `enrichments` | Mapped to enrichment entries |

---

## FAQ

**Q: Can I run OpenSOAR alongside TheHive during migration?**
Yes. Point your SIEM to send alerts to both platforms during the transition. OpenSOAR's webhook endpoint (`POST /api/v1/webhooks/alerts`) accepts the same JSON payloads — you may just need to adjust field names.

**Q: What about my Cortex analyzers?**
OpenSOAR ships with VirusTotal, AbuseIPDB, Slack, Email, and Elastic integrations. For other analyzers, rewrite them as Python playbooks — it's typically less code than a Cortex analyzer since there's no Docker packaging overhead.

**Q: I used TheHive4py extensively. Is there an OpenSOAR client?**
OpenSOAR exposes a standard REST API. Use `httpx` or `requests` directly. The API is documented via OpenAPI at `/docs` when running the server.

**Q: Will my Elasticsearch alert feeders still work?**
Yes. OpenSOAR has a dedicated Elastic webhook endpoint (`POST /api/v1/webhooks/alerts/elastic`) that understands Elastic Security alert payloads natively.

**Q: What about TheHive 5 (commercial) users?**
The same migration process applies. TheHive 5's API is backward-compatible with v0/v1. Export via the API and import to OpenSOAR.

---

## Getting Help

- **Issues**: [github.com/opensoar-platform/core/issues](https://github.com/opensoar-platform/core/issues)
- **Discussions**: [github.com/opensoar-platform/core/discussions](https://github.com/opensoar-platform/core/discussions)

If you're migrating a large TheHive deployment and hit edge cases, open an issue. We want to make this path smooth.
