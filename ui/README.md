# OpenSOAR UI

React frontend for the OpenSOAR SOAR platform — built for SOC analysts doing alert triage and incident response.

**OpenSOAR is a PwnKit Labs product.**

## Stack

- React 19 + TypeScript
- Vite 8
- Tailwind CSS v4
- framer-motion (animations)
- TanStack React Query (data fetching)
- Lucide React (icons)

## Development

```bash
# From the repo root
cd ui
npm install
npm run dev
```

The dev server runs on `http://localhost:5173` and proxies API calls to `http://localhost:8000`.

## Pages

- **Dashboard** — Priority queue, MTTR, unassigned alerts, per-partner stats
- **Alerts** — Filterable list with bulk actions (resolve, assign, set determination)
- **Alert Detail** — Single-scroll layout with IOCs, timeline, playbook runs, activity log
- **Playbooks** — Management and run history with expandable action steps
- **Settings** — Integration config, API keys, analyst management

## Design

- Dark theme only (optimized for SOC environments)
- 12-column grid layout
- Custom component library inspired by shadcn/ui
- No tabs on alert detail — everything visible on one page for fast triage

## Docker

Built as a separate Docker target (`ui`) in the monorepo Dockerfile:

```bash
docker build --target ui -t opensoar-core-ui .
```

Image: `ghcr.io/opensoar-hq/opensoar-core-ui:latest`
