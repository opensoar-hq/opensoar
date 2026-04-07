from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.rbac import Permission, require_permission
from opensoar.core.decorators import get_playbook_registry
from opensoar.models.alert import Alert
from opensoar.models.analyst import Analyst
from opensoar.models.playbook import PlaybookDefinition
from opensoar.plugins import apply_tenant_access_query, enforce_tenant_access
from opensoar.schemas.playbook import PlaybookResponse, PlaybookRunRequest, PlaybookUpdate

router = APIRouter(prefix="/playbooks", tags=["playbooks"])


@router.get("", response_model=list[PlaybookResponse])
async def list_playbooks(
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.PLAYBOOKS_READ)),
):
    query = select(PlaybookDefinition).order_by(
        PlaybookDefinition.execution_order,
        PlaybookDefinition.name,
    )
    query = await apply_tenant_access_query(
        request.app,
        query=query,
        resource_type="playbook",
        action="list",
        analyst=analyst,
        request=request,
        session=session,
    )
    result = await session.execute(query)
    playbooks = result.scalars().all()
    return [PlaybookResponse.model_validate(pb) for pb in playbooks]


@router.get("/{playbook_id}", response_model=PlaybookResponse)
async def get_playbook(
    playbook_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.PLAYBOOKS_READ)),
):
    result = await session.execute(
        select(PlaybookDefinition).where(PlaybookDefinition.id == playbook_id)
    )
    pb = result.scalar_one_or_none()
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    await enforce_tenant_access(
        request.app,
        resource=pb,
        resource_type="playbook",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )
    return PlaybookResponse.model_validate(pb)


@router.patch("/{playbook_id}", response_model=PlaybookResponse)
async def update_playbook(
    playbook_id: uuid.UUID,
    update: PlaybookUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.PLAYBOOKS_MANAGE)),
):
    result = await session.execute(
        select(PlaybookDefinition).where(PlaybookDefinition.id == playbook_id)
    )
    pb = result.scalar_one_or_none()
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pb, field, value)
    await enforce_tenant_access(
        request.app,
        resource=pb,
        resource_type="playbook",
        action="update",
        analyst=analyst,
        request=request,
        session=session,
    )

    await session.commit()
    await session.refresh(pb)
    return PlaybookResponse.model_validate(pb)


@router.post("/{playbook_id}/run")
async def run_playbook(
    playbook_id: uuid.UUID,
    run_request: PlaybookRunRequest | None = None,
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.PLAYBOOKS_EXECUTE)),
):
    result = await session.execute(
        select(PlaybookDefinition).where(PlaybookDefinition.id == playbook_id)
    )
    pb_def = result.scalar_one_or_none()
    if not pb_def:
        raise HTTPException(status_code=404, detail="Playbook not found")
    await enforce_tenant_access(
        request.app,
        resource=pb_def,
        resource_type="playbook",
        action="run",
        analyst=analyst,
        request=request,
        session=session,
    )

    registry = get_playbook_registry()
    pb = registry.get(pb_def.name)
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not loaded in registry")

    from opensoar.worker.tasks import execute_playbook_task

    alert_id = str(run_request.alert_id) if run_request and run_request.alert_id else None
    if run_request and run_request.alert_id:
        alert = (
            await session.execute(select(Alert).where(Alert.id == run_request.alert_id))
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
        if analyst is not None and analyst.role != "admin" and pb_def.partner != alert.partner:
            raise HTTPException(status_code=403, detail="Playbook tenant scope does not match alert")
    task = execute_playbook_task.delay(pb_def.name, alert_id)

    return {
        "message": f"Playbook '{pb_def.name}' triggered",
        "celery_task_id": task.id,
    }
