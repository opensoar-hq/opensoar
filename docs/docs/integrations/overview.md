---
icon: lucide/plug
---

# Integrations Overview

OpenSOAR ships with a small set of built-in integrations and is designed to be extended in Python.

## Current Approach

Integrations are Python classes, not marketplace-only black boxes.

That means you can:

- read the code
- test behavior locally
- extend connectors
- build your own adapters without learning a proprietary plugin format first

## Typical Use in Playbooks

Playbooks call integrations as part of enrichment, notification, and response steps.

Common examples:

- pull threat intel
- notify Slack
- send email
- fetch alerts from upstream tools
- execute response actions

## Configuration

Integration configuration is handled through the OpenSOAR platform and environment-specific secrets, depending on the connector.

## Related Areas

- [Playbooks Overview](../playbooks/overview.md)
- [API Overview](../api/overview.md)
