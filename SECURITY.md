# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in OpenSOAR, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, email **security@opensoar.app** with:

1. Description of the vulnerability
2. Steps to reproduce
3. Affected versions
4. Impact assessment (if known)

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 5 business days
- **Fix or mitigation**: Depends on severity, but we aim for:
  - Critical: 72 hours
  - High: 1 week
  - Medium/Low: Next release cycle

## Disclosure Policy

We follow coordinated disclosure:

1. Reporter notifies us privately
2. We confirm and assess the vulnerability
3. We develop and test a fix
4. We release the fix and publish an advisory
5. Reporter is credited (unless they prefer anonymity)

We ask that you give us reasonable time to address the issue before public disclosure.

## Scope

This policy applies to:
- `opensoar-core` (API, worker, UI)
- `opensoar-sdk`
- `opensoar-deploy`
- Official Docker images on GHCR

Third-party integrations should be reported to their respective maintainers.
