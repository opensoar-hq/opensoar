---
icon: lucide/code-2
---

# Playbooks Overview

OpenSOAR playbooks are plain Python modules. The system discovers them from configured directories and registers them through decorators at import time.

## Basic Structure

```python
from opensoar import playbook, action, resolve_current_alert
import asyncio


@action(name="enrich_ip", timeout=30, retries=2, retry_backoff=2.0)
async def enrich_ip(ip: str | None) -> dict:
    if not ip:
        return {"status": "missing"}
    return {"status": "ok", "ip": ip}


@playbook(
    trigger="webhook",
    conditions={"severity": ["high", "critical"]},
    description="Enrich and triage high-severity alerts",
)
async def triage_high_severity(alert_data):
    result = await enrich_ip(alert_data.get("source_ip"))
    if result.get("status") == "ok":
        await resolve_current_alert(
            determination="benign",
            reason="Issue remediated automatically by playbook",
        )
    return {"enrichment": result}
```

## Core Concepts

### `@playbook`

The `@playbook` decorator defines:

- trigger type
- matching conditions
- optional description
- whether the playbook is enabled
- optional execution `order`

### `@action`

The `@action` decorator wraps a step with:

- execution tracking
- timeout handling
- retries
- backoff

### Parallel Execution

Use normal Python async patterns:

```python
vt_result, abuse_result = await asyncio.gather(
    lookup_virustotal(iocs),
    lookup_abuseipdb(source_ip),
)
```

### Explicit Execution Order

When multiple playbooks match the same alert, OpenSOAR executes them in ascending `order`.

```python
@playbook(
    trigger="webhook",
    conditions={"tags": ["docker"]},
    order=10,
)
async def prepare_docker_recovery(alert_data):
    ...


@playbook(
    trigger="webhook",
    conditions={"tags": ["docker"]},
    order=20,
)
async def restart_docker_service(alert_data):
    ...
```

Lower numbers run first. The default is `1000`, so only set `order` when the sequence matters operationally.

### Resolving The Current Alert

When a playbook is running for a specific alert, it can resolve that bound alert directly:

```python
from opensoar import resolve_current_alert

await resolve_current_alert(
    determination="benign",
    reason="Issue remediated automatically by playbook",
)
```

This is the supported path for automation that wants to mark the current alert as resolved after remediation succeeds.

### Updating The Current Alert Without Resolving It

If a playbook finishes its own automation but wants a human to continue, use the generic helper:

```python
from opensoar import update_current_alert

await update_current_alert(
    status="in_progress",
    determination="suspicious",
    reason="Playbook completed triage but needs analyst follow-up",
)
```

Use this when the automation has done useful work but the alert should stay open.

### Commenting On The Current Alert

If a playbook wants to leave a note for the next human or for auditability:

```python
from opensoar import add_current_alert_comment

await add_current_alert_comment(
    "Playbook completed triage and left this for analyst follow-up",
)
```

### Assigning The Current Alert

If a playbook wants to hand the current alert to a specific analyst:

```python
from opensoar import assign_current_alert

await assign_current_alert(username="dutyanalyst")
```

Calling `assign_current_alert()` with no arguments unassigns the current alert.

For the broader status/determination model, read [Alert Lifecycle](../alerts/lifecycle.md).

## Recommended Workflow

1. Write a playbook in `playbooks/` or another configured directory.
2. Test it like normal Python code.
3. Start or restart the API and worker so the playbook is discovered consistently.
4. Confirm it appears in the playbooks API or UI.
5. Trigger it with a matching alert.

The API and UI expose the persisted `execution_order`, and the playbooks list is returned in that order.

## What OpenSOAR Does Not Have Yet

- no dedicated playbook upload API
- no dedicated playbook UI publishing workflow
- no separate sync button for playbooks

For the current loading model, read [Loading and Syncing Playbooks](loading-and-sync.md).
