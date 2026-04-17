from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.jwt import get_current_analyst, require_analyst
from opensoar.plugins import enforce_tenant_access
from opensoar.models.activity import Activity
from opensoar.models.alert import Alert
from opensoar.models.analyst import Analyst
from opensoar.schemas.activity import ActivityList, ActivityResponse, CommentCreate, CommentUpdate

router = APIRouter(prefix="/alerts", tags=["activities"])


@router.get("/{alert_id}/activities", response_model=ActivityList)
async def list_alert_activities(
    alert_id: uuid.UUID,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    alert = (
        await session.execute(select(Alert).where(Alert.id == alert_id))
    ).scalar_one_or_none()
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
        select(Activity)
        .where(Activity.alert_id == alert_id)
        .order_by(Activity.created_at.desc())
    )
    count_query = select(func.count(Activity.id)).where(Activity.alert_id == alert_id)

    total = (await session.execute(count_query)).scalar() or 0
    result = await session.execute(query.offset(offset).limit(limit))
    activities = result.scalars().all()

    return ActivityList(
        activities=[ActivityResponse.model_validate(a) for a in activities],
        total=total,
    )


@router.post("/{alert_id}/comments", response_model=ActivityResponse)
async def add_comment(
    alert_id: uuid.UUID,
    body: CommentCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_analyst),
):
    # Verify alert exists
    alert = (
        await session.execute(select(Alert).where(Alert.id == alert_id))
    ).scalar_one_or_none()
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

    activity = Activity(
        alert_id=alert_id,
        analyst_id=analyst.id,
        analyst_username=analyst.username,
        action="comment",
        detail=body.text,
    )
    session.add(activity)
    await session.commit()
    await session.refresh(activity)
    return ActivityResponse.model_validate(activity)


@router.patch("/{alert_id}/comments/{comment_id}", response_model=ActivityResponse)
async def edit_comment(
    alert_id: uuid.UUID,
    comment_id: uuid.UUID,
    body: CommentUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_analyst),
):
    """Edit a comment. Only the author can edit. Stores edit history in metadata_json."""
    alert = (
        await session.execute(select(Alert).where(Alert.id == alert_id))
    ).scalar_one_or_none()
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

    activity = (
        await session.execute(
            select(Activity).where(
                Activity.id == comment_id,
                Activity.alert_id == alert_id,
                Activity.action == "comment",
            )
        )
    ).scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Comment not found")

    if activity.analyst_id != analyst.id:
        raise HTTPException(status_code=403, detail="Can only edit your own comments")

    # Store previous version in edit history
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
