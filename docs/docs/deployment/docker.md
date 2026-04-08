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
- `JWT_SECRET` and `API_KEY_SECRET` must both be set to non-empty values or startup will fail fast

## Production Advice

Treat playbooks like application code:

- version them in Git
- review them in pull requests
- deploy them alongside the services that execute them
- restart the relevant services in a controlled way

If you want a future “upload playbook” experience, that should be designed as an explicit product feature rather than inferred from the current Docker model.

## Upgrade Procedure

For the packaged self-hosted path:

```bash
docker compose -f deploy/docker-compose.yml pull
docker compose -f deploy/docker-compose.yml up -d
```

That keeps the `migrate`, `api`, `worker`, and `ui` images aligned during the upgrade.

## Post-Upgrade Validation

After an upgrade:

1. Confirm the API health endpoint returns `status: ok`.
2. Check `docker compose ps` and confirm `api`, `worker`, `postgres`, and `redis` are up.
3. Review `docker compose logs migrate api worker --tail 100`.
4. Confirm API startup logs still show expected playbook discovery.
5. Send a low-risk webhook test and confirm the worker still executes queued automation.

## Backup and Rollback Guidance

- Back up Postgres before upgrades that may apply new Alembic revisions.
- Do not assume image rollback alone is safe after migrations have already run.
- If rollback is required after a migration, restore the database and keep `migrate`, `api`, and `worker` on the same application/plugin image set.
