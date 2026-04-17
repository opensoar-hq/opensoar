"""Admin endpoints for data retention management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.rbac import Permission, require_permission
from opensoar.models.analyst import Analyst
from opensoar.plugins import dispatch_audit_event
from opensoar.retention.service import run_retention_purge
from opensoar.schemas.audit import AuditEvent

router = APIRouter(prefix="/admin/retention", tags=["admin", "retention"])


@router.post("/purge")
async def purge_retention(
    request: Request,
    dry_run: bool = True,
    session: AsyncSession = Depends(get_db),
    admin: Analyst = Depends(require_permission(Permission.RETENTION_MANAGE)),
) -> dict:
    """Soft-delete resources past their retention threshold, hard-delete those
    past the grace period. Use ``dry_run=true`` (default) to preview counts."""
    result = await run_retention_purge(
        session,
        dry_run=dry_run,
        actor_username=admin.username,
        actor_id=admin.id,
    )

    await dispatch_audit_event(
        request.app,
        AuditEvent(
            category="admin",
            action="retention.purge" if not dry_run else "retention.purge.dry_run",
            actor_id=admin.id,
            actor_username=admin.username,
            target_type="retention",
            metadata_json=result,
        ),
    )
    return result
