# Self-Hosted Packaging

This directory now owns the public self-hosted packaging entry points for OpenSOAR.

## Deployment Paths

### Docker Compose

For the simplest single-host deployment, use the bundled Compose file:

```bash
docker compose -f deploy/docker-compose.yml up -d
```

This path runs:

- `postgres`
- `redis`
- `migrate`
- `api`
- `worker`
- `ui`

### Helm

The first Kubernetes packaging slice lives at:

```bash
helm/opensoar
```

Install it with:

```bash
helm install opensoar ./helm/opensoar
```

The chart currently deploys:

- `postgres` as a single-replica StatefulSet
- `redis` as a single-replica Deployment
- `migrate` as a pre-install / pre-upgrade Job
- `api`
- `worker`
- `ui`

## Packaging Caveats

- The chart is intentionally a v0 skeleton, not a HA reference architecture.
- The current UI image proxies `/api` to the Kubernetes Service named `api`, so the chart assumes one OpenSOAR release per namespace.
- EE-compatible self-hosted installs should override the `api`, `worker`, and `migrate` images with custom images that include the private `opensoar-ee` package.
- Secret values in `values.yaml` are placeholders. Use real secrets before production deployment.
- Elasticsearch / Kibana are not bundled in the Helm chart. Integrate those as external dependencies if your environment needs them.

## Upgrade Posture

- Migrations run as a Helm hook Job before install and upgrade.
- Persistent data is only defined for Postgres in this first slice.
- Review image tags carefully before upgrading from `latest` to a pinned release or vice versa.

## Upgrade Checklist

Before upgrading a self-hosted deployment:

1. Back up the Postgres data volume or database instance.
2. Decide whether you are upgrading to pinned image tags or continuing to track `latest`.
3. Make sure `api`, `worker`, and `migrate` all use the same application/plugin image set.
4. Review any local playbook or plugin changes you expect the new deployment to load.

### Docker Compose Upgrade

Use:

```bash
docker compose -f deploy/docker-compose.yml pull
docker compose -f deploy/docker-compose.yml up -d
```

After the upgrade:

1. Check `docker compose ps`.
2. Confirm the API is healthy:

```bash
curl http://localhost:8000/api/v1/health
```

3. Check `docker compose logs migrate api worker --tail 100`.
4. Confirm playbooks are still discovered in the API startup logs.
5. Trigger a low-risk webhook test and confirm the worker still processes playbook execution.

### Helm Upgrade

Use:

```bash
helm upgrade --install opensoar ./helm/opensoar
```

After the upgrade:

1. Confirm the migrate hook Job completed successfully.
2. Confirm `api`, `worker`, and `ui` Pods are Ready.
3. Confirm the API health endpoint responds through your Service/Ingress path.
4. Confirm startup logs still show expected playbook discovery.
5. Trigger a low-risk webhook test and confirm the worker still consumes queued work.

## Rollback Notes

- Database schema migrations can make rollback asymmetric. Do not assume you can safely roll back application images without checking the migration history first.
- If a migration has already run, prefer restoring from a database backup over blindly reverting only the `api`/`worker` images.
- If you ship optional plugins or private extensions, treat rollback as a full image-set rollback across `api`, `worker`, and `migrate`, not a single-service change.

## Recommended Next Hardening Steps

- externalize Postgres and Redis for production
- add ingress, TLS, and secret-manager integration
- pin image tags per release
- add probes, resource requests/limits, and backup guidance tuned for your environment
