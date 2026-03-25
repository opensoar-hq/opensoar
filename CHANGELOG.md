# Changelog

All notable changes to OpenSOAR are documented here.

## [Unreleased]

### Added
- RBAC with fine-grained permissions (3 roles, 15 permissions) and audit logging
- Plugin architecture for loading optional enterprise features
- AI Tier 2: playbook generation, auto-resolve, LLM-powered correlation
- AI Tier 1: model-agnostic LLM client (Claude, OpenAI, Ollama), alert summarization, triage recommendations
- Case management: incidents, observables, correlation engine
- Incidents and observables UI pages
- Dynamic integration loader with health checks and available types API
- Webhook API key authentication
- Scheduler and playbook enable/disable controls
- Rate limiting and structured logging
- 168+ test suite with CI pipeline (test, lint, Docker multi-target build)
- React 19 dashboard with dark theme, priority queue, MTTR, per-partner MSSP stats
- Alert detail view with triage, IOCs, timeline, playbook runs
- Core platform: alert management, playbook engine (`@playbook`/`@action` decorators), trigger engine
- Webhook ingestion with normalization (Elastic, generic JSON), IOC extraction, deduplication
- Integrations: Elastic Security, VirusTotal, AbuseIPDB, Slack, Email
- Celery-based async playbook execution with horizontal scaling
- Docker multi-target build (api, worker, migrate, ui) published to GHCR
