---
icon: lucide/shield
---

# OpenSOAR Documentation

OpenSOAR is an open-source SOAR platform built around Python-native playbooks, case management, integrations, and async execution.

This site is the canonical documentation for OpenSOAR. It covers both product usage and contributor-facing engineering references.

## Start Here

- [Getting Started](getting-started.md)
- [Playbooks Overview](playbooks/overview.md)
- [Loading and Syncing Playbooks](playbooks/loading-and-sync.md)
- [Docker Deployment](deployment/docker.md)
- [Integrations Overview](integrations/overview.md)
- [API Overview](api/overview.md)
- [Migrate from TheHive](migrations/thehive.md)
- [Playbook Troubleshooting](troubleshooting/playbooks.md)
- [Engineering Overview](engineering/index.md)

## Product Boundaries

OpenSOAR currently follows a playbooks-as-code model:

- playbooks are Python files
- playbooks are discovered from configured directories
- there is no separate playbook upload API or UI yet
- database migrations are handled by the `migrate` service, not by the playbook loader

That distinction matters because a lot of first-time setup confusion comes from assuming playbooks are uploaded or synchronized through the database migration flow. They are not.

## Repositories

- `opensoar-core`: API, worker, UI, playbook engine, database models
- `opensoar-www`: marketing site

## Need the Source?

- Core repo: <https://github.com/opensoar-hq/opensoar-core>
- Main site: <https://opensoar.app>
