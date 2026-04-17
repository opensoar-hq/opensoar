from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.jwt import get_current_analyst
from opensoar.auth.rbac import Permission, require_permission
from opensoar.plugins import apply_tenant_access_query, enforce_tenant_access
from opensoar.models.activity import Activity
from opensoar.models.alert import Alert
from opensoar.models.analyst import Analyst
from opensoar.models.incident import Incident
from opensoar.models.incident_alert import IncidentAlert
from opensoar.models.observable import Observable
from opensoar.schemas.activity import (
    ActivityList,
    ActivityResponse,
    CommentCreate,
    CommentUpdate,
    TimelineEvent,
    TimelineList,
)
from opensoar.schemas.alert import AlertResponse
from opensoar.schemas.incident import (
    IncidentCreate,
    IncidentList,
    IncidentResponse,
    IncidentUpdate,
    LinkAlertRequest,
)
from opensoar.schemas.observable import ObservableCreate, ObservableResponse

router = APIRouter(prefix="/incidents", tags=["incidents"])


async def _incident_response(
    session: AsyncSession, incident: Incident
) -> IncidentResponse:
    """Build an IncidentResponse with alert_count from the IncidentAlert table."""
    count_query = select(func.count(IncidentAlert.id)).where(
        IncidentAlert.incident_id == incident.id
    )
    alert_count = (await session.execute(count_query)).scalar() or 0
    resp = IncidentResponse.model_validate(incident)
    resp.alert_count = alert_count
    return resp


def _incident_activity_detail(action: str, incident_title: str, alert_title: str | None = None) -> str:
    if action == "incident_created":
        return f"Incident created: {incident_title}"
    if action == "status_change":
        return incident_title
    if action == "severity_change":
        return incident_title
    if action == "assigned":
        return incident_title
    if action == "comment":
        return incident_title
    if action == "alert_linked" and alert_title:
        return f"Linked alert {alert_title}"
    if action == "alert_unlinked" and alert_title:
        return f"Unlinked alert {alert_title}"
    return incident_title


def _append_incident_activity(
    session: AsyncSession,
    *,
    incident_id: uuid.UUID,
    analyst: Analyst | None,
    action: str,
    detail: str,
    metadata_json: dict | None = None,
    alert_id: uuid.UUID | None = None,
) -> None:
    session.add(
        Activity(
            alert_id=alert_id,
            incident_id=incident_id,
            analyst_id=analyst.id if analyst else None,
            analyst_username=analyst.username if analyst else None,
            action=action,
            detail=detail,
            metadata_json=metadata_json,
        )
    )


@router.get("/suggestions")
async def incident_suggestions(
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    """Basic correlation: group unlinked alerts by source_ip, return groups with 2+ alerts."""
    # Find alerts that have no incident link
    linked_alert_ids = select(IncidentAlert.alert_id)
    query = (
        select(Alert.source_ip, func.count(Alert.id).label("count"))
        .where(Alert.id.notin_(linked_alert_ids))
        .where(Alert.source_ip.isnot(None))
        .group_by(Alert.source_ip)
        .having(func.count(Alert.id) >= 2)
    )
    query = await apply_tenant_access_query(
        request.app,
        query=query,
        resource_type="alert",
        action="incident_suggestions",
        analyst=analyst,
        request=request,
        session=session,
    )
    result = await session.execute(query)
    groups = []
    for row in result.all():
        # Fetch the actual alerts in this group
        alerts_query = (
            select(Alert)
            .where(Alert.source_ip == row.source_ip)
            .where(Alert.id.notin_(linked_alert_ids))
            .order_by(Alert.created_at.desc())
        )
        alerts_query = await apply_tenant_access_query(
            request.app,
            query=alerts_query,
            resource_type="alert",
            action="incident_suggestions",
            analyst=analyst,
            request=request,
            session=session,
        )
        alerts_result = await session.execute(alerts_query)
        alerts = alerts_result.scalars().all()
        groups.append({
            "source_ip": row.source_ip,
            "alert_count": row.count,
            "alerts": [AlertResponse.model_validate(a) for a in alerts],
        })
    return groups


@router.get("", response_model=IncidentList)
async def list_incidents(
    status: str | None = None,
    severity: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    query = select(Incident).order_by(Incident.created_at.desc())
    count_query = select(func.count(Incident.id))

    if status:
        query = query.where(Incident.status == status)
        count_query = count_query.where(Incident.status == status)
    if severity:
        query = query.where(Incident.severity == severity)
        count_query = count_query.where(Incident.severity == severity)

    query = await apply_tenant_access_query(
        request.app,
        query=query,
        resource_type="incident",
        action="list",
        analyst=analyst,
        request=request,
        session=session,
    )
    count_query = await apply_tenant_access_query(
        request.app,
        query=count_query,
        resource_type="incident",
        action="count",
        analyst=analyst,
        request=request,
        session=session,
    )

    total = (await session.execute(count_query)).scalar() or 0
    result = await session.execute(query.offset(offset).limit(limit))
    incidents = result.scalars().all()

    responses = []
    for inc in incidents:
        responses.append(await _incident_response(session, inc))

    return IncidentList(incidents=responses, total=total)


@router.post("", response_model=IncidentResponse, status_code=201)
async def create_incident(
    data: IncidentCreate,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.INCIDENTS_CREATE)),
):
    incident = Incident(
        title=data.title,
        description=data.description,
        severity=data.severity,
        tags=data.tags,
    )
    session.add(incident)
    await session.flush()
    _append_incident_activity(
        session,
        incident_id=incident.id,
        analyst=analyst,
        action="incident_created",
        detail=_incident_activity_detail("incident_created", incident.title),
        metadata_json={"incident_title": incident.title},
    )
    await session.commit()
    await session.refresh(incident)
    return await _incident_response(session, incident)


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    result = await session.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    await enforce_tenant_access(
        request.app,
        resource=incident,
        resource_type="incident",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )
    return await _incident_response(session, incident)


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: uuid.UUID,
    update: IncidentUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.INCIDENTS_UPDATE)),
):
    result = await session.execute(
        select(Incident).where(Incident.id == incident_id)
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

    update_data = update.model_dump(exclude_unset=True)
    old_status = incident.status
    old_severity = incident.severity
    old_assigned_to = incident.assigned_to
    old_assigned_username = incident.assigned_username

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
                incident.assigned_to = assigned_analyst.id
                incident.assigned_username = assigned_analyst.username
        else:
            incident.assigned_to = None
            incident.assigned_username = None

    for field, value in update_data.items():
        setattr(incident, field, value)

    # Set closed_at when status changes to closed
    if update.status == "closed" and not incident.closed_at:
        incident.closed_at = datetime.now(timezone.utc)
    elif update.status and update.status != "closed":
        incident.closed_at = None

    if update.status and update.status != old_status:
        _append_incident_activity(
            session,
            incident_id=incident.id,
            analyst=analyst,
            action="status_change",
            detail=f"Status changed from {old_status} to {update.status}",
            metadata_json={"old": old_status, "new": update.status},
        )

    if update.severity and update.severity != old_severity:
        _append_incident_activity(
            session,
            incident_id=incident.id,
            analyst=analyst,
            action="severity_change",
            detail=f"Severity changed from {old_severity} to {update.severity}",
            metadata_json={"old": old_severity, "new": update.severity},
        )

    if "assigned_to" in update_data or update.assigned_to is not None or (
        update.assigned_to is None and old_assigned_to is not None and "assigned_to" in update.model_fields_set
    ):
        if incident.assigned_to != old_assigned_to:
            if incident.assigned_to and incident.assigned_username:
                detail = f"Assigned to {incident.assigned_username}"
            else:
                detail = (
                    f"Unassigned from {old_assigned_username}"
                    if old_assigned_username
                    else "Unassigned"
                )
            _append_incident_activity(
                session,
                incident_id=incident.id,
                analyst=analyst,
                action="assigned",
                detail=detail,
                metadata_json={
                    "old": str(old_assigned_to) if old_assigned_to else None,
                    "new": str(incident.assigned_to) if incident.assigned_to else None,
                    "old_username": old_assigned_username,
                    "new_username": incident.assigned_username,
                },
            )

    await session.commit()
    await session.refresh(incident)
    return await _incident_response(session, incident)


@router.post("/{incident_id}/alerts", status_code=201)
async def link_alert(
    incident_id: uuid.UUID,
    body: LinkAlertRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.INCIDENTS_UPDATE)),
):
    # Verify incident exists
    result = await session.execute(
        select(Incident).where(Incident.id == incident_id)
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

    # Verify alert exists
    alert_uuid = uuid.UUID(body.alert_id)
    result = await session.execute(select(Alert).where(Alert.id == alert_uuid))
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

    # Check if already linked
    existing = await session.execute(
        select(IncidentAlert).where(
            IncidentAlert.incident_id == incident_id,
            IncidentAlert.alert_id == alert_uuid,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Alert already linked to this incident")

    link = IncidentAlert(incident_id=incident_id, alert_id=alert_uuid)
    session.add(link)
    _append_incident_activity(
        session,
        incident_id=incident_id,
        alert_id=alert_uuid,
        analyst=analyst,
        action="alert_linked",
        detail=f"Linked alert {alert.title}",
        metadata_json={"alert_id": str(alert.id), "alert_title": alert.title},
    )
    await session.commit()
    return {"detail": "Alert linked to incident"}


@router.get("/{incident_id}/alerts")
async def list_incident_alerts(
    incident_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    # Verify incident exists
    result = await session.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    await enforce_tenant_access(
        request.app,
        resource=incident,
        resource_type="incident",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )

    query = (
        select(Alert)
        .join(IncidentAlert, IncidentAlert.alert_id == Alert.id)
        .where(IncidentAlert.incident_id == incident_id)
        .order_by(Alert.created_at.desc())
    )
    query = await apply_tenant_access_query(
        request.app,
        query=query,
        resource_type="alert",
        action="list",
        analyst=analyst,
        request=request,
        session=session,
    )
    result = await session.execute(query)
    alerts = result.scalars().all()
    return [AlertResponse.model_validate(a) for a in alerts]


@router.delete("/{incident_id}/alerts/{alert_id}")
async def unlink_alert(
    incident_id: uuid.UUID,
    alert_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.INCIDENTS_UPDATE)),
):
    result = await session.execute(
        select(IncidentAlert).where(
            IncidentAlert.incident_id == incident_id,
            IncidentAlert.alert_id == alert_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    await enforce_tenant_access(
        request.app,
        resource=link,
        resource_type="incident_alert",
        action="update",
        analyst=analyst,
        request=request,
        session=session,
    )

    alert = (
        await session.execute(select(Alert).where(Alert.id == alert_id))
    ).scalar_one_or_none()
    incident = (
        await session.execute(select(Incident).where(Incident.id == incident_id))
    ).scalar_one_or_none()

    if incident and alert:
        _append_incident_activity(
            session,
            incident_id=incident_id,
            alert_id=alert_id,
            analyst=analyst,
            action="alert_unlinked",
            detail=f"Unlinked alert {alert.title}",
            metadata_json={"alert_id": str(alert.id), "alert_title": alert.title},
        )
    await session.delete(link)
    await session.commit()
    return {"detail": "Alert unlinked from incident"}


@router.get("/{incident_id}/observables", response_model=list[ObservableResponse])
async def list_incident_observables(
    incident_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    incident = (
        await session.execute(select(Incident).where(Incident.id == incident_id))
    ).scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    await enforce_tenant_access(
        request.app,
        resource=incident,
        resource_type="incident",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )

    query = (
        select(Observable)
        .where(Observable.incident_id == incident_id)
        .order_by(Observable.created_at.desc())
    )
    query = await apply_tenant_access_query(
        request.app,
        query=query,
        resource_type="observable",
        action="list",
        analyst=analyst,
        request=request,
        session=session,
    )
    result = await session.execute(query)
    observables = result.scalars().all()
    return [ObservableResponse.model_validate(observable) for observable in observables]


@router.post("/{incident_id}/observables", response_model=ObservableResponse, status_code=201)
async def create_incident_observable(
    incident_id: uuid.UUID,
    data: ObservableCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.OBSERVABLES_MANAGE)),
):
    incident = (
        await session.execute(select(Incident).where(Incident.id == incident_id))
    ).scalar_one_or_none()
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

    existing = await session.execute(
        select(Observable).where(
            Observable.type == data.type,
            Observable.value == data.value,
            Observable.incident_id == incident_id,
        )
    )
    observable = existing.scalar_one_or_none()
    if observable:
        return ObservableResponse.model_validate(observable)

    observable = Observable(
        type=data.type,
        value=data.value,
        source=data.source,
        incident_id=incident_id,
    )
    await enforce_tenant_access(
        request.app,
        resource=observable,
        resource_type="observable",
        action="create",
        analyst=analyst,
        request=request,
        session=session,
    )
    session.add(observable)
    await session.flush()
    _append_incident_activity(
        session,
        incident_id=incident_id,
        analyst=analyst,
        action="observable_added",
        detail=f"Added observable {data.type}:{data.value}",
        metadata_json={"observable_type": data.type, "observable_value": data.value},
    )
    await session.commit()
    await session.refresh(observable)
    return ObservableResponse.model_validate(observable)


@router.get("/{incident_id}/activities", response_model=ActivityList)
async def list_incident_activities(
    incident_id: uuid.UUID,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    incident = (
        await session.execute(select(Incident).where(Incident.id == incident_id))
    ).scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    await enforce_tenant_access(
        request.app,
        resource=incident,
        resource_type="incident",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )

    query = (
        select(Activity)
        .where(Activity.incident_id == incident_id)
        .order_by(Activity.created_at.desc())
    )
    count_query = select(func.count(Activity.id)).where(Activity.incident_id == incident_id)

    total = (await session.execute(count_query)).scalar() or 0
    result = await session.execute(query.offset(offset).limit(limit))
    activities = result.scalars().all()

    return ActivityList(
        activities=[ActivityResponse.model_validate(a) for a in activities],
        total=total,
    )


@router.get("/{incident_id}/timeline", response_model=TimelineList)
async def list_incident_timeline(
    incident_id: uuid.UUID,
    event_type: str = Query(default="all", pattern="^(all|alert|incident|comment)$"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    """Return a merged chronology of the incident and its linked alerts.

    Events cover incident lifecycle activity (creation, status/severity/assignment
    changes, linking, comments, observables) and activities on every linked alert
    (comments, playbook runs, status changes). Tenant scoping is enforced by
    re-validating the incident and filtering the linked-alert set through the
    registered tenant validators, matching the pattern used elsewhere in this
    router so optional plugins can scope results.
    """
    incident = (
        await session.execute(select(Incident).where(Incident.id == incident_id))
    ).scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    await enforce_tenant_access(
        request.app,
        resource=incident,
        resource_type="incident",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )

    # Resolve which linked alerts the caller may see so we don't leak activity
    # from alerts that belong to other tenants.
    linked_alert_query = (
        select(Alert.id)
        .join(IncidentAlert, IncidentAlert.alert_id == Alert.id)
        .where(IncidentAlert.incident_id == incident_id)
    )
    linked_alert_query = await apply_tenant_access_query(
        request.app,
        query=linked_alert_query,
        resource_type="alert",
        action="list",
        analyst=analyst,
        request=request,
        session=session,
    )
    visible_alert_ids = list(
        (await session.execute(linked_alert_query)).scalars().all()
    )

    # Combine activities on the incident with activities on the alerts the
    # caller is allowed to see.
    conditions = [Activity.incident_id == incident_id]
    if visible_alert_ids:
        conditions.append(Activity.alert_id.in_(visible_alert_ids))

    base_where = or_(*conditions)

    query = select(Activity).where(base_where)
    count_query = select(func.count(Activity.id)).where(base_where)

    if event_type == "alert":
        query = query.where(Activity.alert_id.isnot(None))
        count_query = count_query.where(Activity.alert_id.isnot(None))
    elif event_type == "incident":
        query = query.where(
            Activity.incident_id == incident_id,
            Activity.alert_id.is_(None),
        )
        count_query = count_query.where(
            Activity.incident_id == incident_id,
            Activity.alert_id.is_(None),
        )
    elif event_type == "comment":
        query = query.where(Activity.action == "comment")
        count_query = count_query.where(Activity.action == "comment")

    query = query.order_by(Activity.created_at.desc()).offset(offset).limit(limit)

    total = (await session.execute(count_query)).scalar() or 0
    result = await session.execute(query)
    activities = result.scalars().all()

    events: list[TimelineEvent] = []
    for activity in activities:
        source = "alert" if activity.alert_id is not None else "incident"
        events.append(
            TimelineEvent(
                id=activity.id,
                source=source,
                action=activity.action,
                detail=activity.detail,
                created_at=activity.created_at,
                updated_at=activity.updated_at,
                analyst_id=activity.analyst_id,
                analyst_username=activity.analyst_username,
                alert_id=activity.alert_id,
                incident_id=activity.incident_id,
                metadata_json=activity.metadata_json,
            )
        )

    return TimelineList(events=events, total=total)


@router.post("/{incident_id}/comments", response_model=ActivityResponse)
async def add_incident_comment(
    incident_id: uuid.UUID,
    body: CommentCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.INCIDENTS_UPDATE)),
):
    incident = (
        await session.execute(select(Incident).where(Incident.id == incident_id))
    ).scalar_one_or_none()
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

    activity = Activity(
        incident_id=incident_id,
        analyst_id=analyst.id,
        analyst_username=analyst.username,
        action="comment",
        detail=body.text,
    )
    session.add(activity)
    await session.commit()
    await session.refresh(activity)
    return ActivityResponse.model_validate(activity)


@router.patch("/{incident_id}/comments/{comment_id}", response_model=ActivityResponse)
async def edit_incident_comment(
    incident_id: uuid.UUID,
    comment_id: uuid.UUID,
    body: CommentUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.INCIDENTS_UPDATE)),
):
    incident = (
        await session.execute(select(Incident).where(Incident.id == incident_id))
    ).scalar_one_or_none()
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

    activity = (
        await session.execute(
            select(Activity).where(
                Activity.id == comment_id,
                Activity.incident_id == incident_id,
                Activity.action == "comment",
            )
        )
    ).scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Comment not found")

    if activity.analyst_id != analyst.id:
        raise HTTPException(status_code=403, detail="Can only edit your own comments")

    history = (activity.metadata_json or {}).get("edit_history", [])
    history.append({
        "text": activity.detail,
        "edited_at": activity.updated_at.isoformat(),
    })
    activity.metadata_json = {**(activity.metadata_json or {}), "edit_history": history}
    activity.detail = body.text

    await session.commit()
    await session.refresh(activity)
    return ActivityResponse.model_validate(activity)
