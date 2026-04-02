---
icon: lucide/rocket
---

# Getting Started

This guide gets a local OpenSOAR stack running with Docker Compose and explains the minimum mental model you need before writing playbooks.

## What You Get

The default stack starts:

- API
- worker
- PostgreSQL
- Redis
- UI

## Start the Stack

```bash
git clone https://github.com/opensoar-hq/opensoar-core.git
cd opensoar-core
docker compose up -d
```

Then open:

- API: `http://localhost:8000`
- UI: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`

## Send a Test Alert

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "Brute Force Detected",
    "severity": "high",
    "source_ip": "203.0.113.42",
    "hostname": "web-prod-01",
    "tags": ["authentication", "brute-force"]
  }'
```

## How OpenSOAR Thinks About Automation

OpenSOAR does not use a visual playbook builder or a YAML workflow DSL.

Instead:

- a playbook is a Python module
- a trigger is declared with `@playbook(...)`
- tracked steps use `@action(...)`
- parallel work uses `asyncio.gather()`
- playbooks are loaded from configured directories on startup or worker execution

## Next Steps

- Read [Playbooks Overview](playbooks/overview.md)
- Read [Loading and Syncing Playbooks](playbooks/loading-and-sync.md)
- Review [Playbook Troubleshooting](troubleshooting/playbooks.md)
