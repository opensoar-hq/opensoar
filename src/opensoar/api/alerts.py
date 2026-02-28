from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.jwt import get_current_analyst
from opensoar.models.activity import Activity
from opensoar.models.alert import Alert
from opensoar.models.analyst import Analyst
from opensoar.models.playbook_run import PlaybookRun
from opensoar.auth.jwt import require_analyst
from opensoar.schemas.alert import (
    AlertDetailResponse,
    AlertList,
    AlertResponse,
    AlertUpdate,
    BulkAlertUpdate,
    BulkOperationResult,
)
from opensoar.schemas.playbook_run import PlaybookRunList, PlaybookRunResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])

VALID_DETERMINATIONS = {"unknown", "malicious", "suspicious", "benign"}


@router.get("", response_model=AlertList)
async def list_alerts(
    status: str | None = None,
    severity: str | None = None,
    source: str | None = None,
    partner: str | None = None,
    determination: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    query = select(Alert).order_by(Alert.created_at.desc())
    count_query = select(func.count(Alert.id))

    if status:
        query = query.where(Alert.status == status)
        count_query = count_query.where(Alert.status == status)
    if severity:
        query = query.where(Alert.severity == severity)
        count_query = count_query.where(Alert.severity == severity)
    if source:
        query = query.where(Alert.source == source)
        count_query = count_query.where(Alert.source == source)
    if partner:
        query = query.where(Alert.partner == partner)
        count_query = count_query.where(Alert.partner == partner)
    if determination:
        query = query.where(Alert.determination == determination)
        count_query = count_query.where(Alert.determination == determination)

    total = (await session.execute(count_query)).scalar() or 0
    result = await session.execute(query.offset(offset).limit(limit))
    alerts = result.scalars().all()

    return AlertList(
        alerts=[AlertResponse.model_validate(a) for a in alerts],
        total=total,
    )


@router.get("/{alert_id}", response_model=AlertDetailResponse)
async def get_alert(
    alert_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertDetailResponse.model_validate(alert)


@router.get("/{alert_id}/runs", response_model=PlaybookRunList)
async def get_alert_runs(
    alert_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    query = select(PlaybookRun).where(PlaybookRun.alert_id == alert_id).order_by(
        PlaybookRun.created_at.desc()
    )
    result = await session.execute(query)
    runs = result.scalars().all()
    count_query = select(func.count(PlaybookRun.id)).where(PlaybookRun.alert_id == alert_id)
    total = (await session.execute(count_query)).scalar() or 0
    return PlaybookRunList(
        runs=[PlaybookRunResponse.model_validate(r) for r in runs],
        total=total,
    )


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: uuid.UUID,
    update: AlertUpdate,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Validate determination value
    if update.determination and update.determination not in VALID_DETERMINATIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid determination. Must be one of: {', '.join(VALID_DETERMINATIONS)}",
        )

    # Resolving requires a determination other than "unknown"
    if update.status == "resolved":
        effective_determination = update.determination or alert.determination
        if effective_determination == "unknown":
            raise HTTPException(
                status_code=422,
                detail="Cannot resolve an alert with determination 'unknown'. Set a determination first.",
            )

    update_data = update.model_dump(exclude_unset=True)

    # Handle assignment
    if "assigned_to" in update_data:
        assigned_id = update_data.pop("assigned_to")
        if assigned_id:
            assigned_analyst = (
                await session.execute(
                    select(Analyst).where(Analyst.id == uuid.UUID(assigned_id))
                )
            ).scalar_one_or_none()
            if assigned_analyst:
                alert.assigned_to = assigned_analyst.id
                alert.assigned_username = assigned_analyst.username
                session.add(Activity(
                    alert_id=alert_id,
                    analyst_id=analyst.id if analyst else None,
                    analyst_username=analyst.username if analyst else None,
                    action="assigned",
                    detail=f"Assigned to {assigned_analyst.display_name}",
                ))
        else:
            alert.assigned_to = None
            alert.assigned_username = None

    old_status = alert.status
    old_severity = alert.severity
    old_determination = alert.determination

    for field, value in update_data.items():
        setattr(alert, field, value)

    if update.status == "resolved" and not alert.resolved_at:
        alert.resolved_at = datetime.now(timezone.utc)

    # Auto-log activity for status changes
    if update.status and update.status != old_status:
        detail = f"Status changed from {old_status} to {update.status}"
        if update.status == "resolved" and update.resolve_reason:
            detail += f" — {update.resolve_reason}"
        session.add(Activity(
            alert_id=alert_id,
            analyst_id=analyst.id if analyst else None,
            analyst_username=analyst.username if analyst else None,
            action="status_change",
            detail=detail,
            metadata_json={"old": old_status, "new": update.status},
        ))

    # Auto-log determination changes
    if update.determination and update.determination != old_determination:
        session.add(Activity(
            alert_id=alert_id,
            analyst_id=analyst.id if analyst else None,
            analyst_username=analyst.username if analyst else None,
            action="determination_set",
            detail=f"Determination set to {update.determination}"
            + (f" (was {old_determination})" if old_determination != "unknown" else ""),
            metadata_json={"old": old_determination, "new": update.determination},
        ))

    # Auto-log severity changes
    if update.severity and update.severity != old_severity:
        session.add(Activity(
            alert_id=alert_id,
            analyst_id=analyst.id if analyst else None,
            analyst_username=analyst.username if analyst else None,
            action="severity_change",
            detail=f"Severity changed from {old_severity} to {update.severity}",
            metadata_json={"old": old_severity, "new": update.severity},
        ))

    await session.commit()
    await session.refresh(alert)
    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/claim", response_model=AlertResponse)
async def claim_alert(
    alert_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    """Claim an alert for the current analyst."""
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if analyst:
        alert.assigned_to = analyst.id
        alert.assigned_username = analyst.username
        session.add(Activity(
            alert_id=alert_id,
            analyst_id=analyst.id,
            analyst_username=analyst.username,
            action="claimed",
            detail=f"Claimed by {analyst.display_name}",
        ))
    else:
        raise HTTPException(status_code=401, detail="Authentication required to claim alerts")

    if alert.status == "new":
        alert.status = "in_progress"
        session.add(Activity(
            alert_id=alert_id,
            analyst_id=analyst.id,
            analyst_username=analyst.username,
            action="status_change",
            detail="Status changed from new to in_progress",
            metadata_json={"old": "new", "new": "in_progress"},
        ))

    await session.commit()
    await session.refresh(alert)
    return AlertResponse.model_validate(alert)


@router.post("/bulk", response_model=BulkOperationResult)
async def bulk_update_alerts(
    body: BulkAlertUpdate,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_analyst),
):
    """Apply a bulk operation to multiple alerts."""
    updated = 0
    failed = 0
    errors: list[str] = []

    result = await session.execute(
        select(Alert).where(Alert.id.in_(body.alert_ids))
    )
    alerts = {a.id: a for a in result.scalars().all()}

    for aid in body.alert_ids:
        alert = alerts.get(aid)
        if not alert:
            failed += 1
            errors.append(f"Alert {aid} not found")
            continue

        try:
            if body.action == "resolve":
                if alert.status == "resolved":
                    continue
                # Bulk resolve requires determination
                determination = body.determination or alert.determination
                if determination == "unknown":
                    failed += 1
                    errors.append(f"Alert {aid}: cannot resolve with unknown determination")
                    continue
                old_status = alert.status
                alert.status = "resolved"
                alert.resolved_at = datetime.now(timezone.utc)
                if body.resolve_reason:
                    alert.resolve_reason = body.resolve_reason
                if body.determination:
                    alert.determination = body.determination
                session.add(Activity(
                    alert_id=aid,
                    analyst_id=analyst.id,
                    analyst_username=analyst.username,
                    action="status_change",
                    detail=f"Bulk resolved (was {old_status})"
                    + (f" — {body.resolve_reason}" if body.resolve_reason else ""),
                    metadata_json={"old": old_status, "new": "resolved"},
                ))

            elif body.action == "assign":
                alert.assigned_to = analyst.id
                alert.assigned_username = analyst.username
                if alert.status == "new":
                    alert.status = "in_progress"
                session.add(Activity(
                    alert_id=aid,
                    analyst_id=analyst.id,
                    analyst_username=analyst.username,
                    action="claimed",
                    detail=f"Bulk assigned to {analyst.display_name}",
                ))

            elif body.action == "change_severity" and body.severity:
                old = alert.severity
                alert.severity = body.severity
                session.add(Activity(
                    alert_id=aid,
                    analyst_id=analyst.id,
                    analyst_username=analyst.username,
                    action="severity_change",
                    detail=f"Bulk severity change from {old} to {body.severity}",
                    metadata_json={"old": old, "new": body.severity},
                ))

            else:
                failed += 1
                errors.append(f"Unknown action: {body.action}")
                continue

            updated += 1
        except Exception as e:
            failed += 1
            errors.append(f"Alert {aid}: {e}")

    await session.commit()
    return BulkOperationResult(updated=updated, failed=failed, errors=errors)


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    await session.delete(alert)
    await session.commit()
    return {"detail": "Alert deleted"}
