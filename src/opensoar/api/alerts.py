from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.jwt import get_current_analyst, require_analyst
from opensoar.auth.rbac import Permission, has_permission, require_permission
from opensoar.models.activity import Activity
from opensoar.models.alert import Alert
from opensoar.models.analyst import Analyst
from opensoar.models.incident import Incident
from opensoar.models.incident_alert import IncidentAlert
from opensoar.models.playbook_run import PlaybookRun
from opensoar.plugins import apply_tenant_access_query, enforce_tenant_access
from opensoar.schemas.alert import (
    AlertIncidentRequest,
    AlertDetailResponse,
    AlertList,
    AlertResponse,
    AlertUpdate,
    BulkAlertUpdate,
    BulkOperationResult,
)
from opensoar.schemas.incident import IncidentResponse
from opensoar.schemas.playbook_run import PlaybookRunList, PlaybookRunResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])

VALID_DETERMINATIONS = {"unknown", "malicious", "suspicious", "benign"}


async def _incident_response(
    session: AsyncSession, incident: Incident
) -> IncidentResponse:
    count_query = select(func.count(IncidentAlert.id)).where(
        IncidentAlert.incident_id == incident.id
    )
    alert_count = (await session.execute(count_query)).scalar() or 0
    resp = IncidentResponse.model_validate(incident)
    resp.alert_count = alert_count
    return resp


@router.get("", response_model=AlertList)
async def list_alerts(
    status: str | None = None,
    severity: str | None = None,
    source: str | None = None,
    partner: str | None = None,
    tenant_id: str | None = None,
    determination: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
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

    query = await apply_tenant_access_query(
        request.app,
        query=query,
        resource_type="alert",
        action="list",
        analyst=analyst,
        request=request,
        session=session,
    )
    count_query = await apply_tenant_access_query(
        request.app,
        query=count_query,
        resource_type="alert",
        action="count",
        analyst=analyst,
        request=request,
        session=session,
    )

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
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await enforce_tenant_access(
        request.app,
        resource=alert,
        resource_type="alert",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )
    return AlertDetailResponse.model_validate(alert)


@router.get("/{alert_id}/runs", response_model=PlaybookRunList)
async def get_alert_runs(
    alert_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    alert = (await session.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await enforce_tenant_access(
        request.app,
        resource=alert,
        resource_type="alert",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )

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


@router.get("/{alert_id}/incidents", response_model=list[IncidentResponse])
async def get_alert_incidents(
    alert_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await enforce_tenant_access(
        request.app,
        resource=alert,
        resource_type="alert",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )

    query = (
        select(Incident)
        .join(IncidentAlert, IncidentAlert.incident_id == Incident.id)
        .where(IncidentAlert.alert_id == alert_id)
        .order_by(Incident.created_at.desc())
    )
    query = await apply_tenant_access_query(
        request.app,
        query=query,
        resource_type="incident",
        action="list",
        analyst=analyst,
        request=request,
        session=session,
    )

    result = await session.execute(query)
    incidents = result.scalars().all()
    return [await _incident_response(session, incident) for incident in incidents]


@router.post("/{alert_id}/incidents", response_model=IncidentResponse, status_code=201)
async def create_or_link_incident_for_alert(
    alert_id: uuid.UUID,
    data: AlertIncidentRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_analyst),
):
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await enforce_tenant_access(
        request.app,
        resource=alert,
        resource_type="alert",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )

    created_new_incident = False

    if data.incident_id:
        if not has_permission(analyst.role, Permission.INCIDENTS_UPDATE):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: requires {Permission.INCIDENTS_UPDATE}",
            )

        result = await session.execute(
            select(Incident).where(Incident.id == uuid.UUID(data.incident_id))
        )
        incident = result.scalar_one_or_none()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        await enforce_tenant_access(
            request.app,
            resource=incident,
            resource_type="incident",
            action="update",
            analyst=analyst,
            request=request,
            session=session,
        )
    else:
        if not has_permission(analyst.role, Permission.INCIDENTS_CREATE):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: requires {Permission.INCIDENTS_CREATE}",
            )

        incident = Incident(
            title=(data.title or "").strip(),
            description=data.description,
            severity=data.severity,
            tags=data.tags,
        )
        session.add(incident)
        await session.flush()
        created_new_incident = True

    existing = await session.execute(
        select(IncidentAlert).where(
            IncidentAlert.incident_id == incident.id,
            IncidentAlert.alert_id == alert_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Alert already linked to this incident")

    if created_new_incident:
        session.add(
            Activity(
                incident_id=incident.id,
                analyst_id=analyst.id,
                analyst_username=analyst.username,
                action="incident_created",
                detail=f"Incident created: {incident.title}",
                metadata_json={"incident_title": incident.title},
            )
        )

    session.add(IncidentAlert(incident_id=incident.id, alert_id=alert_id))
    session.add(
        Activity(
            alert_id=alert_id,
            incident_id=incident.id,
            analyst_id=analyst.id,
            analyst_username=analyst.username,
            action="incident_linked",
            detail=(
                f"Created and linked incident {incident.title}"
                if created_new_incident
                else f"Linked to incident {incident.title}"
            ),
            metadata_json={
                "incident_id": str(incident.id),
                "incident_title": incident.title,
                "created_new_incident": created_new_incident,
            },
        )
    )

    await session.commit()
    await session.refresh(incident)
    return await _incident_response(session, incident)


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: uuid.UUID,
    update: AlertUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.ALERTS_UPDATE)),
):
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await enforce_tenant_access(
        request.app,
        resource=alert,
        resource_type="alert",
        action="update",
        analyst=analyst,
        request=request,
        session=session,
    )

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
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.ALERTS_UPDATE)),
):
    """Claim an alert for the current analyst."""
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await enforce_tenant_access(
        request.app,
        resource=alert,
        resource_type="alert",
        action="claim",
        analyst=analyst,
        request=request,
        session=session,
    )

    alert.assigned_to = analyst.id
    alert.assigned_username = analyst.username
    session.add(Activity(
        alert_id=alert_id,
        analyst_id=analyst.id,
        analyst_username=analyst.username,
        action="claimed",
        detail=f"Claimed by {analyst.display_name}",
    ))

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
    analyst: Analyst = Depends(require_permission(Permission.ALERTS_UPDATE)),
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
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.ALERTS_DELETE)),
):
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    await enforce_tenant_access(
        request.app,
        resource=alert,
        resource_type="alert",
        action="delete",
        analyst=analyst,
        request=request,
        session=session,
    )

    await session.delete(alert)
    await session.commit()
    return {"detail": "Alert deleted"}
