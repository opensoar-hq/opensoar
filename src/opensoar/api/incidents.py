from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.jwt import get_current_analyst
from opensoar.models.alert import Alert
from opensoar.models.analyst import Analyst
from opensoar.models.incident import Incident
from opensoar.models.incident_alert import IncidentAlert
from opensoar.schemas.alert import AlertResponse
from opensoar.schemas.incident import (
    IncidentCreate,
    IncidentList,
    IncidentResponse,
    IncidentUpdate,
    LinkAlertRequest,
)

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


@router.get("/suggestions")
async def incident_suggestions(
    session: AsyncSession = Depends(get_db),
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
    session: AsyncSession = Depends(get_db),
):
    query = select(Incident).order_by(Incident.created_at.desc())
    count_query = select(func.count(Incident.id))

    if status:
        query = query.where(Incident.status == status)
        count_query = count_query.where(Incident.status == status)
    if severity:
        query = query.where(Incident.severity == severity)
        count_query = count_query.where(Incident.severity == severity)

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
    analyst: Analyst | None = Depends(get_current_analyst),
):
    incident = Incident(
        title=data.title,
        description=data.description,
        severity=data.severity,
        tags=data.tags,
    )
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return await _incident_response(session, incident)


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return await _incident_response(session, incident)


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: uuid.UUID,
    update: IncidentUpdate,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    result = await session.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

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

    await session.commit()
    await session.refresh(incident)
    return await _incident_response(session, incident)


@router.post("/{incident_id}/alerts", status_code=201)
async def link_alert(
    incident_id: uuid.UUID,
    body: LinkAlertRequest,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    # Verify incident exists
    result = await session.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Incident not found")

    # Verify alert exists
    alert_uuid = uuid.UUID(body.alert_id)
    result = await session.execute(select(Alert).where(Alert.id == alert_uuid))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Alert not found")

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
    await session.commit()
    return {"detail": "Alert linked to incident"}


@router.get("/{incident_id}/alerts")
async def list_incident_alerts(
    incident_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    # Verify incident exists
    result = await session.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Incident not found")

    query = (
        select(Alert)
        .join(IncidentAlert, IncidentAlert.alert_id == Alert.id)
        .where(IncidentAlert.incident_id == incident_id)
        .order_by(Alert.created_at.desc())
    )
    result = await session.execute(query)
    alerts = result.scalars().all()
    return [AlertResponse.model_validate(a) for a in alerts]


@router.delete("/{incident_id}/alerts/{alert_id}")
async def unlink_alert(
    incident_id: uuid.UUID,
    alert_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
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

    await session.delete(link)
    await session.commit()
    return {"detail": "Alert unlinked from incident"}
