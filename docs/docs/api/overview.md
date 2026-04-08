---
icon: lucide/braces
---

# API Overview

OpenSOAR exposes a FastAPI-based API for alerts, playbooks, runs, integrations, incidents, authentication, and supporting workflows.

## Local API Docs

When the stack is running locally:

```text
http://localhost:8000/docs
```

## Relevant Playbook Endpoints

Examples:

- `GET /api/v1/playbooks`
- `GET /api/v1/playbooks/{playbook_id}`
- `PATCH /api/v1/playbooks/{playbook_id}`
- `POST /api/v1/playbooks/{playbook_id}/run`

## Important Limitation

These endpoints operate on discovered playbook definitions. They do not replace the code-on-disk workflow for authoring and loading playbooks.

In other words:

- you can list playbooks through the API
- you can toggle enablement through the API
- you can trigger a discovered playbook through the API
- you cannot upload a new Python playbook through the API today

For the operational loading model, read [Loading and Syncing Playbooks](../playbooks/loading-and-sync.md).

## Relevant Incident Endpoints

Examples:

- `GET /api/v1/incidents`
- `POST /api/v1/incidents`
- `PATCH /api/v1/incidents/{incident_id}`
- `GET /api/v1/incidents/{incident_id}/activities`
- `POST /api/v1/incidents/{incident_id}/comments`
- `GET /api/v1/incidents/{incident_id}/alerts`
- `POST /api/v1/incidents/{incident_id}/alerts`
- `GET /api/v1/incidents/{incident_id}/observables`
- `POST /api/v1/incidents/{incident_id}/observables`
- `GET /api/v1/incidents/suggestions`

For the operator workflow around those endpoints, read [Incident Workflow](../incidents/overview.md).

## Webhook Ingestion

OpenSOAR can ingest alerts through webhook endpoints under `/api/v1/webhooks/...`, then normalize and route them into playbook execution.
