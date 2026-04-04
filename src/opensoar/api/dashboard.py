from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.jwt import get_current_analyst
from opensoar.models.alert import Alert
from opensoar.models.analyst import Analyst
from opensoar.models.playbook_run import PlaybookRun
from opensoar.plugins import apply_tenant_access_query
from opensoar.schemas.alert import AlertResponse
from opensoar.schemas.playbook_run import PlaybookRunResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def dashboard_stats(
    request: Request,
    tenant_id: str | None = None,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # Alerts by severity
    sev_q = select(Alert.severity, func.count(Alert.id)).group_by(Alert.severity)
    sev_q = await apply_tenant_access_query(
        request.app,
        query=sev_q,
        resource_type="alert",
        action="dashboard_stats",
        analyst=analyst,
        request=request,
        session=session,
    )
    sev_result = await session.execute(sev_q)
    alerts_by_severity = dict(sev_result.all())

    # Alerts by status
    status_q = select(Alert.status, func.count(Alert.id)).group_by(Alert.status)
    status_q = await apply_tenant_access_query(
        request.app,
        query=status_q,
        resource_type="alert",
        action="dashboard_stats",
        analyst=analyst,
        request=request,
        session=session,
    )
    status_result = await session.execute(status_q)
    alerts_by_status = dict(status_result.all())

    # Alerts by partner (for MSSP billing)
    partner_q = (
        select(Alert.partner, func.count(Alert.id))
        .where(Alert.partner.is_not(None))
        .group_by(Alert.partner)
    )
    partner_q = await apply_tenant_access_query(
        request.app,
        query=partner_q,
        resource_type="alert",
        action="dashboard_stats",
        analyst=analyst,
        request=request,
        session=session,
    )
    partner_result = await session.execute(partner_q)
    alerts_by_partner = dict(partner_result.all())

    # Alerts by determination
    det_q = select(Alert.determination, func.count(Alert.id)).group_by(Alert.determination)
    det_q = await apply_tenant_access_query(
        request.app,
        query=det_q,
        resource_type="alert",
        action="dashboard_stats",
        analyst=analyst,
        request=request,
        session=session,
    )
    det_result = await session.execute(det_q)
    alerts_by_determination = dict(det_result.all())

    # MTTR by partner (for MSSP SLA tracking)
    mttr_by_partner_q = (
        select(
            Alert.partner,
            func.avg(
                func.extract("epoch", Alert.resolved_at) - func.extract("epoch", Alert.created_at)
            ),
        )
        .where(
            Alert.partner.is_not(None),
            Alert.resolved_at.is_not(None),
            Alert.resolved_at >= week_ago,
        )
        .group_by(Alert.partner)
    )
    mttr_by_partner_q = await apply_tenant_access_query(
        request.app,
        query=mttr_by_partner_q,
        resource_type="alert",
        action="dashboard_stats",
        analyst=analyst,
        request=request,
        session=session,
    )
    mttr_partner_result = await session.execute(mttr_by_partner_q)
    mttr_by_partner = {row[0]: row[1] for row in mttr_partner_result.all()}

    # Open alerts by partner
    open_by_partner_q = (
        select(Alert.partner, func.count(Alert.id))
        .where(
            Alert.partner.is_not(None),
            Alert.status.in_(["new", "in_progress"]),
        )
        .group_by(Alert.partner)
    )
    open_by_partner_q = await apply_tenant_access_query(
        request.app,
        query=open_by_partner_q,
        resource_type="alert",
        action="dashboard_stats",
        analyst=analyst,
        request=request,
        session=session,
    )
    open_partner_result = await session.execute(open_by_partner_q)
    open_by_partner = dict(open_partner_result.all())

    # Totals
    total_alerts = sum(alerts_by_severity.values())
    total_runs_q = select(func.count(PlaybookRun.id))
    total_runs = (await session.execute(total_runs_q)).scalar() or 0

    # Open alerts count (new + in_progress)
    open_alerts = (alerts_by_status.get("new", 0) + alerts_by_status.get("in_progress", 0))

    # Alerts created today
    alerts_today_q = select(func.count(Alert.id)).where(
        Alert.created_at >= today_start
    )
    alerts_today_q = await apply_tenant_access_query(
        request.app,
        query=alerts_today_q,
        resource_type="alert",
        action="dashboard_stats",
        analyst=analyst,
        request=request,
        session=session,
    )
    alerts_today = (await session.execute(alerts_today_q)).scalar() or 0

    # MTTR — mean time to resolve for alerts resolved in last 7 days
    mttr_q = select(
        func.avg(
            func.extract("epoch", Alert.resolved_at) - func.extract("epoch", Alert.created_at)
        )
    ).where(
        Alert.resolved_at.is_not(None),
        Alert.resolved_at >= week_ago,
    )
    mttr_q = await apply_tenant_access_query(
        request.app,
        query=mttr_q,
        resource_type="alert",
        action="dashboard_stats",
        analyst=analyst,
        request=request,
        session=session,
    )
    mttr_seconds = (await session.execute(mttr_q)).scalar()

    # Active runs (running/pending)
    active_runs_q = select(func.count(PlaybookRun.id)).where(
        PlaybookRun.status.in_(["running", "pending"])
    )
    active_runs = (await session.execute(active_runs_q)).scalar() or 0

    # Priority queue: open alerts sorted by severity weight, then age
    severity_order = case(
        (Alert.severity == "critical", 0),
        (Alert.severity == "high", 1),
        (Alert.severity == "medium", 2),
        (Alert.severity == "low", 3),
        else_=4,
    )
    priority_q = (
        select(Alert)
        .where(Alert.status.in_(["new", "in_progress"]))
        .order_by(severity_order, Alert.created_at.asc())
        .limit(10)
    )
    priority_q = await apply_tenant_access_query(
        request.app,
        query=priority_q,
        resource_type="alert",
        action="dashboard_stats",
        analyst=analyst,
        request=request,
        session=session,
    )
    priority_alerts = (await session.execute(priority_q)).scalars().all()

    # My assignments (if authenticated)
    my_alerts: list[AlertResponse] = []
    if analyst:
        my_q = (
            select(Alert)
            .where(
                Alert.assigned_to == analyst.id,
                Alert.status.in_(["new", "in_progress"]),
            )
            .order_by(severity_order, Alert.created_at.asc())
            .limit(10)
        )
        my_q = await apply_tenant_access_query(
            request.app,
            query=my_q,
            resource_type="alert",
            action="dashboard_stats",
            analyst=analyst,
            request=request,
            session=session,
        )
        my_result = (await session.execute(my_q)).scalars().all()
        my_alerts = [AlertResponse.model_validate(a) for a in my_result]

    # Recent runs
    recent_runs_q = select(PlaybookRun).order_by(PlaybookRun.created_at.desc()).limit(5)
    recent_runs = (await session.execute(recent_runs_q)).scalars().all()

    # Unassigned open alerts count
    unassigned_q = select(func.count(Alert.id)).where(
        Alert.status.in_(["new", "in_progress"]),
        Alert.assigned_to.is_(None),
    )
    unassigned_q = await apply_tenant_access_query(
        request.app,
        query=unassigned_q,
        resource_type="alert",
        action="dashboard_stats",
        analyst=analyst,
        request=request,
        session=session,
    )
    unassigned_count = (await session.execute(unassigned_q)).scalar() or 0

    return {
        "alerts_by_severity": alerts_by_severity,
        "alerts_by_status": alerts_by_status,
        "alerts_by_partner": alerts_by_partner,
        "alerts_by_determination": alerts_by_determination,
        "open_by_partner": open_by_partner,
        "mttr_by_partner": mttr_by_partner,
        "total_alerts": total_alerts,
        "total_runs": total_runs,
        "open_alerts": open_alerts,
        "alerts_today": alerts_today,
        "active_runs": active_runs,
        "unassigned_count": unassigned_count,
        "mttr_seconds": mttr_seconds,
        "priority_queue": [AlertResponse.model_validate(a) for a in priority_alerts],
        "my_alerts": my_alerts,
        "recent_runs": [PlaybookRunResponse.model_validate(r) for r in recent_runs],
        # Keep backwards compat
        "recent_alerts": [AlertResponse.model_validate(a) for a in priority_alerts[:5]],
    }
