---
icon: lucide/list-checks
---

# Alert Lifecycle

This page defines the intended alert lifecycle in OpenSOAR and how analysts and playbooks are expected to use it.

The goal is simple:

- alerts should move through a clear workflow
- determination should be explicit
- automation should update alert state in a way that stays understandable to humans

## Statuses

OpenSOAR uses three core alert statuses:

- `new`
- `in_progress`
- `resolved`

### `new`

Use `new` when:

- an alert has just been ingested
- no analyst or playbook has claimed ownership yet
- no meaningful triage or remediation work has happened yet

This is the default ingest state.

### `in_progress`

Use `in_progress` when:

- an analyst has claimed or been assigned the alert
- a playbook has completed an initial triage step, but a human still needs to continue
- remediation is underway, but the alert should remain open

This is the correct status for “automation did useful work, but the case is not done.”

### `resolved`

Use `resolved` when:

- investigation or remediation is complete
- the alert should leave the active queue
- the final determination is known

`resolved` is the terminal state in the core alert workflow.

## Determination

Status and determination are related, but they are not the same thing.

Supported determinations are:

- `unknown`
- `malicious`
- `suspicious`
- `benign`

### Important rule

An alert cannot be resolved while its determination is `unknown`.

That rule exists so every resolved alert leaves an auditable judgment behind.

Examples:

- `status = in_progress`, `determination = suspicious`
  This means the playbook or analyst has done some triage and the alert still needs follow-up.

- `status = resolved`, `determination = benign`
  This means the issue is understood and closed as non-malicious.

- `status = resolved`, `determination = malicious`
  This means the issue was real and the response is considered complete.

## Recommended Playbook Usage

When a playbook runs for a bound alert, prefer the supported helpers from `opensoar`:

- `resolve_current_alert(...)`
- `update_current_alert(...)`

### Resolve after successful remediation

```python
from opensoar import resolve_current_alert

await resolve_current_alert(
    determination="benign",
    reason="Issue remediated automatically by playbook",
)
```

### Leave open for human follow-up

```python
from opensoar import update_current_alert

await update_current_alert(
    status="in_progress",
    determination="suspicious",
    reason="Playbook completed triage but needs analyst follow-up",
)
```

## Recommended Analyst Usage

### Manual triage

- keep the alert as `new` if no one is actually working it yet
- move to `in_progress` when ownership is taken or meaningful investigation starts
- move to `resolved` only when the work is done and the determination is clear

### Assignment

- assignment usually implies real ownership
- in practice, assigned alerts should usually end up `in_progress`

## Common Patterns

### Auto-remediation succeeded

- set determination
- resolve the alert

Typical outcome:
- `status = resolved`
- `determination = benign` or `malicious`, depending on what happened

### Automation escalated to a specialist

- move to `in_progress`
- set a useful determination if one is already known
- leave a comment or assignment if needed

Typical outcome:
- `status = in_progress`
- `determination = suspicious`

### Playbook could not help

- do not leave the alert as `new` if the playbook already performed meaningful triage
- update it to `in_progress` so the queue reflects that work has already started

## Anti-Patterns

Avoid:

- resolving an alert with `determination = unknown`
- leaving an alert as `new` after meaningful automated triage already happened
- using raw HTTP calls back into the API from playbooks for basic current-alert state transitions when supported helpers exist

## Related Docs

- [Playbooks Overview](../playbooks/overview.md)
- [Authentication and SSO](../deployment/authentication.md)
- [Engineering Design Decisions](../engineering/design-decisions.md)
