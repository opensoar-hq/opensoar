---
icon: lucide/shield
---

# Overview

OpenSOAR is an open-source SOAR platform built around Python-native playbooks, case management, integrations, and async execution.

This is the canonical documentation site for OpenSOAR. Use it as the map for product docs, operations guidance, and contributor-facing engineering references.

## What To Read First

- [Getting Started](getting-started.md)
- [Playbooks Overview](playbooks/overview.md)
- [Loading and Syncing Playbooks](playbooks/loading-and-sync.md)
- [Docker Deployment](deployment/docker.md)

## Docs Map

- **Getting Started**: local setup and first-run flow
- **Playbooks**: how automation is written and loaded
- **Deployment**: runtime and operational guidance
- **Integrations**: connector model and usage
- **API**: endpoint overview
- **Migrations**: moving from TheHive
- **Troubleshooting**: common playbook issues
- **Engineering**: architecture and contributor references

If you are new to OpenSOAR, start with [Getting Started](getting-started.md). If you are already running it and need a specific topic, use the left navigation.

## Important Product Boundaries

OpenSOAR currently follows a playbooks-as-code model:

- playbooks are Python files
- playbooks are discovered from configured directories
- there is no separate playbook upload API or UI yet
- database migrations are handled by the `migrate` service, not by the playbook loader

That distinction matters because a lot of first-time confusion comes from assuming playbooks are uploaded or synchronized through the database migration flow. They are not.

## Repositories

- `opensoar-core`: API, worker, UI, playbook engine, database models
- `opensoar-www`: marketing site

## Need the Source?

- Core repo: <https://github.com/opensoar-hq/opensoar-core>
- Main site: <https://opensoar.app>
