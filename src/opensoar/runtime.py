from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from opensoar.core.decorators import get_execution_context
from opensoar.db import async_session
from opensoar.models.activity import Activity
from opensoar.models.alert import Alert

VALID_ALERT_STATUSES = {"new", "in_progress", "resolved"}
VALID_DETERMINATIONS = {"unknown", "malicious", "suspicious", "benign"}


def get_current_alert_id() -> str | None:
    ctx = get_execution_context()
    if ctx is None or ctx.alert_id is None:
        return None
    return str(ctx.alert_id)


def _apply_alert_update(
    session,
    alert: Alert,
    *,
    status: str | None,
    determination: str | None,
    reason: str | None,
    partner: str | None,
    activity_action: str | None,
    activity_detail: str | None,
    activity_metadata: dict[str, Any] | None,
) -> None:
    old_status = alert.status
    old_determination = alert.determination

    if status is not None:
        alert.status = status
    if determination is not None:
        alert.determination = determination
    if alert.status == "resolved":
        alert.resolved_at = alert.resolved_at or datetime.now(timezone.utc)
    if reason is not None:
        alert.resolve_reason = reason
    if partner is not None:
        alert.partner = partner

    if alert.status != old_status:
        session.add(
            Activity(
                alert_id=alert.id,
                action="status_change",
                detail=f"Status changed from {old_status} to {alert.status}"
                + (f" — {reason}" if reason else ""),
                metadata_json={"old": old_status, "new": alert.status, "source": "playbook"},
            )
        )

    if determination is not None and old_determination != determination:
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


async def update_current_alert(
    *,
    status: str | None = None,
    determination: str | None = None,
    reason: str | None = None,
    partner: str | None = None,
    activity_action: str | None = None,
    activity_detail: str | None = None,
    activity_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update the alert bound to the current playbook execution context."""

    if status is None and determination is None and reason is None and partner is None:
        raise ValueError("At least one alert field must be updated")

    if status is not None and status not in VALID_ALERT_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(VALID_ALERT_STATUSES))}")

    if determination is not None and determination not in VALID_DETERMINATIONS:
        raise ValueError(f"determination must be one of: {', '.join(sorted(VALID_DETERMINATIONS))}")

    effective_status = status
    effective_determination = determination
    if effective_status == "resolved":
        if effective_determination is None:
            effective_determination = "unknown"
        if effective_determination == "unknown":
            raise ValueError("resolving an alert requires a determination other than 'unknown'")

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
        _apply_alert_update(
            session,
            alert,
            status=effective_status,
            determination=effective_determination,
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
            _apply_alert_update(
                session,
                alert,
                status=effective_status,
                determination=effective_determination,
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

    return await update_current_alert(
        status="resolved",
        determination=determination,
        reason=reason,
        partner=partner,
        activity_action=activity_action,
        activity_detail=activity_detail,
        activity_metadata=activity_metadata,
    )
