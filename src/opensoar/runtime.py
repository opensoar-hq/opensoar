from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from opensoar.core.decorators import get_execution_context
from opensoar.db import async_session
from opensoar.models.activity import Activity
from opensoar.models.alert import Alert

VALID_DETERMINATIONS = {"unknown", "malicious", "suspicious", "benign"}


def get_current_alert_id() -> str | None:
    ctx = get_execution_context()
    if ctx is None or ctx.alert_id is None:
        return None
    return str(ctx.alert_id)


def _apply_resolution(
    session,
    alert: Alert,
    *,
    determination: str,
    reason: str | None,
    partner: str | None,
    activity_action: str | None,
    activity_detail: str | None,
    activity_metadata: dict[str, Any] | None,
) -> None:
    old_status = alert.status
    old_determination = alert.determination

    alert.status = "resolved"
    alert.determination = determination
    alert.resolved_at = alert.resolved_at or datetime.now(timezone.utc)
    if reason is not None:
        alert.resolve_reason = reason
    if partner is not None:
        alert.partner = partner

    session.add(
        Activity(
            alert_id=alert.id,
            action="status_change",
            detail=f"Status changed from {old_status} to resolved"
            + (f" — {reason}" if reason else ""),
            metadata_json={"old": old_status, "new": "resolved", "source": "playbook"},
        )
    )

    if old_determination != determination:
        session.add(
            Activity(
                alert_id=alert.id,
                action="determination_set",
                detail=f"Determination set to {determination}"
                + (f" (was {old_determination})" if old_determination != "unknown" else ""),
                metadata_json={
                    "old": old_determination,
                    "new": determination,
                    "source": "playbook",
                },
            )
        )

    if activity_action and activity_detail:
        session.add(
            Activity(
                alert_id=alert.id,
                action=activity_action,
                detail=activity_detail,
                metadata_json=activity_metadata or {"source": "playbook"},
            )
        )


async def resolve_current_alert(
    *,
    determination: str,
    reason: str | None = None,
    partner: str | None = None,
    activity_action: str | None = None,
    activity_detail: str | None = None,
    activity_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the alert bound to the current playbook execution context."""

    if determination not in (VALID_DETERMINATIONS - {"unknown"}):
        raise ValueError("determination must be one of: benign, suspicious, malicious")

    ctx = get_execution_context()
    if ctx is None or ctx.alert_id is None:
        raise RuntimeError("No current alert is bound to this execution context")

    alert_id = uuid.UUID(str(ctx.alert_id))

    existing_session = ctx.session
    if existing_session is not None:
        session = existing_session
        result = await session.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if alert is None:
            raise RuntimeError("Current alert not found")
        _apply_resolution(
            session,
            alert,
            determination=determination,
            reason=reason,
            partner=partner,
            activity_action=activity_action,
            activity_detail=activity_detail,
            activity_metadata=activity_metadata,
        )
        await session.flush()
    else:
        async with async_session() as session:
            result = await session.execute(select(Alert).where(Alert.id == alert_id))
            alert = result.scalar_one_or_none()
            if alert is None:
                raise RuntimeError("Current alert not found")
            _apply_resolution(
                session,
                alert,
                determination=determination,
                reason=reason,
                partner=partner,
                activity_action=activity_action,
                activity_detail=activity_detail,
                activity_metadata=activity_metadata,
            )
            await session.commit()

    return {
        "alert_id": str(alert.id),
        "status": alert.status,
        "determination": alert.determination,
        "partner": alert.partner,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
    }
