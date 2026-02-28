from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.core.decorators import get_playbook_registry
from opensoar.models.playbook import PlaybookDefinition
from opensoar.schemas.playbook import PlaybookResponse, PlaybookRunRequest, PlaybookUpdate

router = APIRouter(prefix="/playbooks", tags=["playbooks"])


@router.get("", response_model=list[PlaybookResponse])
async def list_playbooks(session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(PlaybookDefinition).order_by(PlaybookDefinition.name)
    )
    playbooks = result.scalars().all()
    return [PlaybookResponse.model_validate(pb) for pb in playbooks]


@router.get("/{playbook_id}", response_model=PlaybookResponse)
async def get_playbook(
    playbook_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(PlaybookDefinition).where(PlaybookDefinition.id == playbook_id)
    )
    pb = result.scalar_one_or_none()
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return PlaybookResponse.model_validate(pb)


@router.patch("/{playbook_id}", response_model=PlaybookResponse)
async def update_playbook(
    playbook_id: uuid.UUID,
    update: PlaybookUpdate,
    session: AsyncSession = Depends(get_db),
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

    await session.commit()
    await session.refresh(pb)
    return PlaybookResponse.model_validate(pb)


@router.post("/{playbook_id}/run")
async def run_playbook(
    playbook_id: uuid.UUID,
    request: PlaybookRunRequest | None = None,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(PlaybookDefinition).where(PlaybookDefinition.id == playbook_id)
    )
    pb_def = result.scalar_one_or_none()
    if not pb_def:
        raise HTTPException(status_code=404, detail="Playbook not found")

    registry = get_playbook_registry()
    pb = registry.get(pb_def.name)
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not loaded in registry")

    from opensoar.worker.tasks import execute_playbook_task

    alert_id = str(request.alert_id) if request and request.alert_id else None
    task = execute_playbook_task.delay(pb_def.name, alert_id)

    return {
        "message": f"Playbook '{pb_def.name}' triggered",
        "celery_task_id": task.id,
    }
