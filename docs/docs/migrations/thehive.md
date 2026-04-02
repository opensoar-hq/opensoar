---
icon: lucide/arrow-right-left
---

# Migrating from TheHive

This guide is intended for teams moving from TheHive to OpenSOAR.

## Concept Mapping

| TheHive | OpenSOAR | Notes |
| --- | --- | --- |
| Alert | Alert | Direct equivalent. |
| Case | Incident | Case management maps to incidents. |
| Observable / Artifact | Observable | IOC storage and enrichment context. |
| Analyzer | Integration + Action | Enrichment and response via OpenSOAR integrations and playbooks. |
| Responder | Playbook | Python-native workflow logic instead of containerized responders. |

## What Changes

The biggest shift is automation style.

In OpenSOAR:

- playbooks are Python
- orchestration logic lives in code
- automation is versioned in Git
- deployment is tied to the playbook codebase and runtime

## Current Gaps to Be Honest About

OpenSOAR is not a drop-in TheHive clone. Depending on your workflow, you may miss:

- some task-oriented case management concepts
- some ecosystem-specific integrations
- parts of the old TheHive/Cortex operating model

## Migration Advice

1. Start with ingestion and triage flows.
2. Port one or two high-value responders into Python playbooks.
3. Validate alert, incident, and observable flows first.
4. Move analysts onto the new operational model only after the basics are stable.

## Next Reading

- [Getting Started](../getting-started.md)
- [Playbooks Overview](../playbooks/overview.md)
- [Loading and Syncing Playbooks](../playbooks/loading-and-sync.md)

If you want the longer migration analysis that originally lived in `opensoar-core`, see [Detailed TheHive Migration Notes](from-thehive-detailed.md).
