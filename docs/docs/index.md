---
icon: lucide/shield
---

# Overview

OpenSOAR is an open-source SOAR platform built around Python-native playbooks, case management, integrations, and async execution.

This is the canonical documentation site for OpenSOAR.

## Start Here

- [Getting Started](getting-started.md)
- [Playbooks](playbooks/overview.md)
- [Loading and Syncing Playbooks](playbooks/loading-and-sync.md)
- [Deployment](deployment/docker.md)
- [Authentication and SSO](deployment/authentication.md)
- [Engineering](engineering/index.md)

## Notes

- Playbooks are code-first Python modules loaded from configured directories.
- The `migrate` service is for database schema migrations, not playbook syncing.
- Third-party auth is not part of the core-only deployment path; see [Authentication and SSO](deployment/authentication.md) for the current status.
- If you need a specific topic beyond the four entry points above, use the left navigation.
