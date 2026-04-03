---
icon: lucide/key-round
---

# Authentication and SSO

This page answers the practical question: what authentication model exists in the public core today, and where does third-party auth fit?

## Community Edition Today

In a core-only deployment, OpenSOAR currently supports:

- local analyst accounts
- username/password login
- JWT-backed UI/API sessions
- API keys for webhook and integration-style access

This is the default path documented in the public repository and the default local Docker workflow.

## Third-Party Auth Status

Third-party analyst authentication is **not** part of the core-only deployment model.

The current public architecture treats SSO and external identity provider support as an optional enterprise plugin surface rather than a built-in core feature.

Practically, that means:

- if you run only `opensoar-core`, you should expect local username/password auth
- if an optional enterprise package is installed, that package can extend the auth surface
- the core login UI can now discover optional external providers through runtime capabilities instead of hardcoded assumptions

## OIDC / Keycloak / Casdoor

The current external-auth direction is OIDC-based provider integration through the optional enterprise path.

For users asking specifically about tools such as:

- Keycloak
- Casdoor
- other OIDC-compatible identity providers

the right model is: configure them as OIDC providers through the optional enterprise auth layer, not through a separate core-only auth mode.

## What This Means Operationally

If you are working in the public core today:

1. use local analyst registration and login
2. use API keys for webhook-style machine access
3. treat external identity provider support as an optional deployment extension, not as part of the default core bootstrap path

## Related Reading

- [Getting Started](../getting-started.md)
- [API Overview](../api/overview.md)
- [Loading and Syncing Playbooks](../playbooks/loading-and-sync.md)
