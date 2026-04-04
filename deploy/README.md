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

## Recommended Next Hardening Steps

- externalize Postgres and Redis for production
- add ingress, TLS, and secret-manager integration
- pin image tags per release
- add probes, resource requests/limits, and backup guidance tuned for your environment
