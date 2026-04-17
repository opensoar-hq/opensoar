"""Role-based access control with fine-grained permissions."""
from __future__ import annotations

from enum import StrEnum

from fastapi import Depends, HTTPException

from opensoar.auth.jwt import get_current_analyst
from opensoar.models.analyst import Analyst


class Permission(StrEnum):
    # Alerts
    ALERTS_READ = "alerts:read"
    ALERTS_UPDATE = "alerts:update"
    ALERTS_DELETE = "alerts:delete"

    # Incidents
    INCIDENTS_READ = "incidents:read"
    INCIDENTS_CREATE = "incidents:create"
    INCIDENTS_UPDATE = "incidents:update"

    # Playbooks
    PLAYBOOKS_READ = "playbooks:read"
    PLAYBOOKS_MANAGE = "playbooks:manage"
    PLAYBOOKS_EXECUTE = "playbooks:execute"

    # Integrations
    INTEGRATIONS_READ = "integrations:read"
    INTEGRATIONS_MANAGE = "integrations:manage"

    # Observables
    OBSERVABLES_READ = "observables:read"
    OBSERVABLES_MANAGE = "observables:manage"

    # AI
    AI_USE = "ai:use"

    # Admin
    ANALYSTS_MANAGE = "analysts:manage"
    API_KEYS_MANAGE = "api_keys:manage"
    SETTINGS_MANAGE = "settings:manage"
    RETENTION_MANAGE = "retention:manage"


CORE_ANALYST_ROLE_LABELS: dict[str, str] = {
    "admin": "Admin",
    "analyst": "Analyst",
    "viewer": "Viewer",
}

ENTERPRISE_ANALYST_ROLE_LABELS: dict[str, str] = {
    "tenant_admin": "Tenant Admin",
    "playbook_author": "Playbook Author",
}

ANALYST_ROLE_LABELS: dict[str, str] = {
    **CORE_ANALYST_ROLE_LABELS,
    **ENTERPRISE_ANALYST_ROLE_LABELS,
}


# Role → Permission mapping
ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "admin": set(Permission),  # All permissions
    "analyst": {
        Permission.ALERTS_READ,
        Permission.ALERTS_UPDATE,
        Permission.ALERTS_DELETE,
        Permission.INCIDENTS_READ,
        Permission.INCIDENTS_CREATE,
        Permission.INCIDENTS_UPDATE,
        Permission.PLAYBOOKS_READ,
        Permission.PLAYBOOKS_EXECUTE,
        Permission.INTEGRATIONS_READ,
        Permission.OBSERVABLES_READ,
        Permission.OBSERVABLES_MANAGE,
        Permission.AI_USE,
    },
    "viewer": {
        Permission.ALERTS_READ,
        Permission.INCIDENTS_READ,
        Permission.PLAYBOOKS_READ,
        Permission.INTEGRATIONS_READ,
        Permission.OBSERVABLES_READ,
    },
    "tenant_admin": {
        Permission.ALERTS_READ,
        Permission.ALERTS_UPDATE,
        Permission.ALERTS_DELETE,
        Permission.INCIDENTS_READ,
        Permission.INCIDENTS_CREATE,
        Permission.INCIDENTS_UPDATE,
        Permission.PLAYBOOKS_READ,
        Permission.PLAYBOOKS_MANAGE,
        Permission.PLAYBOOKS_EXECUTE,
        Permission.INTEGRATIONS_READ,
        Permission.INTEGRATIONS_MANAGE,
        Permission.OBSERVABLES_READ,
        Permission.OBSERVABLES_MANAGE,
        Permission.AI_USE,
    },
    "playbook_author": {
        Permission.ALERTS_READ,
        Permission.INCIDENTS_READ,
        Permission.PLAYBOOKS_READ,
        Permission.PLAYBOOKS_MANAGE,
        Permission.PLAYBOOKS_EXECUTE,
        Permission.INTEGRATIONS_READ,
        Permission.OBSERVABLES_READ,
    },
}

VALID_ANALYST_ROLES = tuple(ROLE_PERMISSIONS.keys())


def has_permission(role: str, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    perms = ROLE_PERMISSIONS.get(role, set())
    return permission in perms


def require_permission(permission: Permission):
    """FastAPI dependency that checks if the current analyst has a permission."""

    async def checker(analyst: Analyst | None = Depends(get_current_analyst)) -> Analyst:
        if analyst is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not has_permission(analyst.role, permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: requires {permission}",
            )
        return analyst

    return checker
