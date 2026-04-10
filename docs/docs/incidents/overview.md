---
icon: lucide/briefcase
---

# Incident Workflow

This page defines how incidents are meant to work in OpenSOAR today.

Incidents are the case-management layer above individual alerts. They exist so analysts can group related alerts, coordinate ownership, leave notes, and track investigation artifacts in one place.

In the current core release, the incident workflow is no longer just an API concept. It is an operator-facing workflow exposed directly in the alert and incident detail pages.

## What an Incident Contains

An incident can now contain:

- linked alerts
- assignment / ownership
- comments and lifecycle timeline events
- incident-scoped observables
- lightweight source-IP-based correlation suggestions from the incidents list

That means the incident page is intended to be the working surface for grouped investigation, not just a static record.

## Core Workflow

### 1. Create or Link from an Alert

When an alert clearly belongs to a broader case, create a new incident from the alert page or link the alert to an existing one.

That keeps the analyst in context and avoids raw UUID copy/paste workflows.

This is the intended escalation path when an alert stops being a single-alert triage task and becomes broader casework.

### 2. Use the Incident as the Working Hub

Once an incident exists, use it to:

- assign ownership
- link additional alerts
- leave comments and handoff notes
- add observables discovered during investigation
- edit your own incident comments when the handoff note or context needs correction

### 3. Track the Timeline

The incident timeline records:

- incident creation
- status changes
- severity changes
- assignment changes
- alert link / unlink actions
- analyst comments
- observable additions

Comments and system activity intentionally share one chronological stream so handoffs stay understandable.

## Assignment

Incident assignment is separate from alert assignment.

Use incident assignment when:

- one analyst owns the overall case
- multiple linked alerts should be managed under one person’s coordination
- handoff needs to be visible at the case level

The assignment action is available directly from the incident detail page.

## Observables

Incident observables are for case-level artifacts that matter across multiple alerts, for example:

- an IP seen across several detections
- a reused phishing domain
- a URL or hash discovered during investigation

They are useful when the observable belongs to the broader case, not just one alert.

## Correlation Suggestions

OpenSOAR currently exposes simple incident suggestions based on unlinked alerts that share the same `source_ip`.

From the incidents list page, analysts can now create an incident directly from a suggested group, which links the grouped alerts into the new case.

This is intentionally a lightweight first slice, not a full correlation engine.

## Current Limitations

Still not available in the core incident workflow:

- case templates
- case-level task checklists
- incident merge flows
- advanced correlation scoring beyond the current lightweight suggestion logic

## Relevant API Endpoints

Examples:

- `GET /api/v1/incidents`
- `POST /api/v1/incidents`
- `PATCH /api/v1/incidents/{incident_id}`
- `GET /api/v1/incidents/{incident_id}/activities`
- `POST /api/v1/incidents/{incident_id}/comments`
- `PATCH /api/v1/incidents/{incident_id}/comments/{comment_id}`
- `GET /api/v1/incidents/{incident_id}/alerts`
- `POST /api/v1/incidents/{incident_id}/alerts`
- `DELETE /api/v1/incidents/{incident_id}/alerts/{alert_id}`
- `GET /api/v1/incidents/{incident_id}/observables`
- `POST /api/v1/incidents/{incident_id}/observables`
- `GET /api/v1/incidents/suggestions`

## Related Docs

- [Alert Lifecycle](../alerts/lifecycle.md)
- [API Overview](../api/overview.md)
- [Playbooks Overview](../playbooks/overview.md)
