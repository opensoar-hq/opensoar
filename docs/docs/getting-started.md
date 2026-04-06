---
icon: lucide/rocket
---

# Getting Started

This guide is the practical setup path: get a local OpenSOAR stack running, confirm the services work, and understand what to do next.

## Before You Start

You need:

- Docker
- Docker Compose
- a clone of `opensoar-core`

## What You Start

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

Bootstrap the first local admin:

```bash
docker compose exec api opensoar-bootstrap-admin \
  --username admin \
  --password changeme \
  --display-name "OpenSOAR Admin"
```

Then open:

- API: `http://localhost:8000`
- UI: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`

When updating an existing Docker Compose install after pulling new code, use:

```bash
docker compose up -d --build
```

That refreshes the migration and app images together so schema changes are applied before the API starts.

## Verify Ingestion

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

If the stack is healthy, the alert should be accepted and routed through the normal ingestion flow.

## Understand The Automation Model

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
- Read [Authentication and SSO](deployment/authentication.md) if you need to understand the current local-auth vs external-auth posture
- Read [Docker Deployment](deployment/docker.md)
- Review [Playbook Troubleshooting](troubleshooting/playbooks.md)
