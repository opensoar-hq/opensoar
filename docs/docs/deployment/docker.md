---
icon: lucide/container
---

# Docker Deployment

The default OpenSOAR deployment is Docker Compose based.

## Services

The standard setup includes:

- `api`
- `worker`
- `postgres`
- `redis`
- `ui`
- `migrate` for schema upgrades during setup flows

## Relevant Environment Variables

```text
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
PLAYBOOK_DIRS=/app/playbooks
JWT_SECRET=...
API_KEY_SECRET=...
```

## Volume Mounts

For local development, the default Compose setup mounts:

- `./src` into the API and worker containers
- `./playbooks` into `/app/playbooks`

That mount is what makes local playbook iteration possible.

## Operational Notes

- restarting `api` refreshes in-process playbook discovery
- restarting `worker` ensures execution uses the latest playbook code
- `migrate` is for Alembic schema migrations only

## Production Advice

Treat playbooks like application code:

- version them in Git
- review them in pull requests
- deploy them alongside the services that execute them
- restart the relevant services in a controlled way

If you want a future “upload playbook” experience, that should be designed as an explicit product feature rather than inferred from the current Docker model.
