---
icon: lucide/refresh-cw
---

# Loading and Syncing Playbooks

This is the part that currently causes the most confusion.

## Current Model

OpenSOAR uses a playbooks-as-code workflow.

You do not upload playbooks into the product through a dedicated API or UI. You place Python modules into a configured playbook directory and OpenSOAR discovers them from there.

## Where Playbooks Live

The platform reads playbooks from `PLAYBOOK_DIRS`.

In the default Docker setup, that is:

```text
/app/playbooks
```

and the local repository folder is mounted into that path.

## What Discovery Means

During startup, the API:

1. reads the configured playbook directories
2. imports Python modules from those directories
3. registers decorated playbooks in memory
4. syncs playbook definitions into the database

The worker also re-discovers playbooks before executing them, which helps keep execution aligned with the code on disk.

## What `migrate` Does

The `migrate` service only handles database schema migrations.

It does **not**:

- discover playbooks
- upload playbooks
- synchronize changed playbook files
- notify the worker about new playbooks

## Safe Operational Guidance

After adding or changing playbooks, the reliable approach is:

1. update the playbook files in the configured directory
2. restart or reload the API
3. restart or reload the worker
4. verify the playbook is listed before relying on it in production

## Verification

You can confirm discovery through:

- the UI playbooks view
- `GET /api/v1/playbooks`
- application logs showing discovered playbooks

## Future Direction

The current model is intentionally code-first, but the documentation should make that much clearer. If a dedicated publishing flow or safer reload mechanism is added later, this page should become the canonical place that documents it.
