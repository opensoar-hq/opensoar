"""Data retention purge service.

Two-phase deletion:

1. **Soft delete** — records that exceed their retention threshold get an
   ``archived_at`` timestamp. They remain in the database during a configurable
   grace period for easy recovery / audit.
2. **Hard delete** — records already archived for longer than the grace period
   are removed from the database.

Every purge writes an Activity row with action ``retention_purge`` carrying the
per-resource counts for audit purposes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.config import settings
from opensoar.models.activity import Activity
from opensoar.models.alert import Alert
from opensoar.models.incident import Incident

logger = logging.getLogger(__name__)

RESOLVED_ALERT_STATUSES = ("resolved", "closed")
CLOSED_INCIDENT_STATUSES = ("closed", "resolved")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _alert_retention_cutoff() -> datetime:
    return _now() - timedelta(days=settings.alerts_retention_days)


def _incident_retention_cutoff() -> datetime:
    return _now() - timedelta(days=settings.incidents_retention_days)


def _activity_retention_cutoff() -> datetime:
    return _now() - timedelta(days=settings.activities_retention_days)


def _grace_cutoff() -> datetime:
    return _now() - timedelta(days=settings.retention_grace_days)


async def _alert_counts(session: AsyncSession) -> dict[str, int]:
    soft_q = select(func.count(Alert.id)).where(
        Alert.archived_at.is_(None),
        Alert.status.in_(RESOLVED_ALERT_STATUSES),
        or_(
            and_(
                Alert.resolved_at.is_not(None),
                Alert.resolved_at < _alert_retention_cutoff(),
            ),
            and_(
                Alert.resolved_at.is_(None),
                Alert.created_at < _alert_retention_cutoff(),
            ),
        ),
    )
    hard_q = select(func.count(Alert.id)).where(
        Alert.archived_at.is_not(None),
        Alert.archived_at < _grace_cutoff(),
    )
    soft = (await session.execute(soft_q)).scalar() or 0
    hard = (await session.execute(hard_q)).scalar() or 0
    return {"soft_delete_candidates": soft, "hard_delete_candidates": hard}


async def _incident_counts(session: AsyncSession) -> dict[str, int]:
    soft_q = select(func.count(Incident.id)).where(
        Incident.archived_at.is_(None),
        Incident.status.in_(CLOSED_INCIDENT_STATUSES),
        or_(
            and_(
                Incident.closed_at.is_not(None),
                Incident.closed_at < _incident_retention_cutoff(),
            ),
            and_(
                Incident.closed_at.is_(None),
                Incident.created_at < _incident_retention_cutoff(),
            ),
        ),
    )
    hard_q = select(func.count(Incident.id)).where(
        Incident.archived_at.is_not(None),
        Incident.archived_at < _grace_cutoff(),
    )
    soft = (await session.execute(soft_q)).scalar() or 0
    hard = (await session.execute(hard_q)).scalar() or 0
    return {"soft_delete_candidates": soft, "hard_delete_candidates": hard}


async def _activity_counts(session: AsyncSession) -> dict[str, int]:
    soft_q = select(func.count(Activity.id)).where(
        Activity.archived_at.is_(None),
        Activity.created_at < _activity_retention_cutoff(),
    )
    hard_q = select(func.count(Activity.id)).where(
        Activity.archived_at.is_not(None),
        Activity.archived_at < _grace_cutoff(),
    )
    soft = (await session.execute(soft_q)).scalar() or 0
    hard = (await session.execute(hard_q)).scalar() or 0
    return {"soft_delete_candidates": soft, "hard_delete_candidates": hard}


async def _soft_delete_alerts(session: AsyncSession, now: datetime) -> int:
    stmt = (
        update(Alert)
        .where(
            Alert.archived_at.is_(None),
            Alert.status.in_(RESOLVED_ALERT_STATUSES),
            or_(
                and_(
                    Alert.resolved_at.is_not(None),
                    Alert.resolved_at < _alert_retention_cutoff(),
                ),
                and_(
                    Alert.resolved_at.is_(None),
                    Alert.created_at < _alert_retention_cutoff(),
                ),
            ),
        )
        .values(archived_at=now)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def _soft_delete_incidents(session: AsyncSession, now: datetime) -> int:
    stmt = (
        update(Incident)
        .where(
            Incident.archived_at.is_(None),
            Incident.status.in_(CLOSED_INCIDENT_STATUSES),
            or_(
                and_(
                    Incident.closed_at.is_not(None),
                    Incident.closed_at < _incident_retention_cutoff(),
                ),
                and_(
                    Incident.closed_at.is_(None),
                    Incident.created_at < _incident_retention_cutoff(),
                ),
            ),
        )
        .values(archived_at=now)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def _soft_delete_activities(session: AsyncSession, now: datetime) -> int:
    stmt = (
        update(Activity)
        .where(
            Activity.archived_at.is_(None),
            Activity.created_at < _activity_retention_cutoff(),
            # Never archive the retention-purge audit rows themselves.
            Activity.action != "retention_purge",
        )
        .values(archived_at=now)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def _hard_delete_alerts(session: AsyncSession) -> int:
    stmt = delete(Alert).where(
        Alert.archived_at.is_not(None),
        Alert.archived_at < _grace_cutoff(),
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def _hard_delete_incidents(session: AsyncSession) -> int:
    stmt = delete(Incident).where(
        Incident.archived_at.is_not(None),
        Incident.archived_at < _grace_cutoff(),
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def _hard_delete_activities(session: AsyncSession) -> int:
    stmt = delete(Activity).where(
        Activity.archived_at.is_not(None),
        Activity.archived_at < _grace_cutoff(),
        Activity.action != "retention_purge",
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def run_retention_purge(
    session: AsyncSession,
    *,
    dry_run: bool = True,
    actor_username: str | None = None,
    actor_id: Any | None = None,
) -> dict[str, Any]:
    """Execute the retention purge.

    When ``dry_run`` is true the session is not mutated and the return value
    contains only candidate counts. Otherwise the function soft-deletes eligible
    records, hard-deletes records beyond the grace period, writes an audit
    Activity row, and commits the transaction.
    """
    logger.info(
        "Retention purge starting (dry_run=%s, actor=%s)", dry_run, actor_username
    )

    alert_counts = await _alert_counts(session)
    incident_counts = await _incident_counts(session)
    activity_counts = await _activity_counts(session)

    result: dict[str, Any] = {
        "dry_run": dry_run,
        "grace_days": settings.retention_grace_days,
        "alerts": dict(alert_counts),
        "incidents": dict(incident_counts),
        "activities": dict(activity_counts),
    }

    if dry_run:
        return result

    now = _now()
    alerts_soft = await _soft_delete_alerts(session, now)
    incidents_soft = await _soft_delete_incidents(session, now)
    activities_soft = await _soft_delete_activities(session, now)

    alerts_hard = await _hard_delete_alerts(session)
    incidents_hard = await _hard_delete_incidents(session)
    activities_hard = await _hard_delete_activities(session)

    result["alerts"].update(
        {"soft_deleted": alerts_soft, "hard_deleted": alerts_hard}
    )
    result["incidents"].update(
        {"soft_deleted": incidents_soft, "hard_deleted": incidents_hard}
    )
    result["activities"].update(
        {"soft_deleted": activities_soft, "hard_deleted": activities_hard}
    )

    audit = Activity(
        action="retention_purge",
        detail=(
            f"Retention purge: alerts soft={alerts_soft} hard={alerts_hard}, "
            f"incidents soft={incidents_soft} hard={incidents_hard}, "
            f"activities soft={activities_soft} hard={activities_hard}"
        ),
        analyst_id=actor_id,
        analyst_username=actor_username,
        metadata_json={
            "alerts": result["alerts"],
            "incidents": result["incidents"],
            "activities": result["activities"],
            "grace_days": settings.retention_grace_days,
        },
    )
    session.add(audit)
    await session.commit()

    logger.info("Retention purge complete: %s", result)
    return result
