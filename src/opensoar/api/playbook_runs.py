from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.models.playbook_run import PlaybookRun
from opensoar.schemas.playbook_run import PlaybookRunList, PlaybookRunResponse

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=PlaybookRunList)
async def list_runs(
    status: str | None = None,
    playbook_id: uuid.UUID | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    query = select(PlaybookRun).order_by(PlaybookRun.created_at.desc())
    count_query = select(func.count(PlaybookRun.id))

    if status:
        query = query.where(PlaybookRun.status == status)
        count_query = count_query.where(PlaybookRun.status == status)
    if playbook_id:
        query = query.where(PlaybookRun.playbook_id == playbook_id)
        count_query = count_query.where(PlaybookRun.playbook_id == playbook_id)

    total = (await session.execute(count_query)).scalar() or 0
    result = await session.execute(query.offset(offset).limit(limit))
    runs = result.scalars().all()

    return PlaybookRunList(
        runs=[PlaybookRunResponse.model_validate(r) for r in runs],
        total=total,
    )


@router.get("/{run_id}", response_model=PlaybookRunResponse)
async def get_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(PlaybookRun).where(PlaybookRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return PlaybookRunResponse.model_validate(run)
