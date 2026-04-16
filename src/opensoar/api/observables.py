from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.jwt import get_current_analyst
from opensoar.auth.rbac import Permission, require_permission
from opensoar.plugins import apply_tenant_access_query, enforce_tenant_access
from opensoar.models.analyst import Analyst
from opensoar.models.observable import Observable
from opensoar.schemas.observable import (
    EnrichmentCreate,
    ObservableCreate,
    ObservableList,
    ObservableResponse,
)

router = APIRouter(prefix="/observables", tags=["observables"])


@router.get("", response_model=ObservableList)
async def list_observables(
    type: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    query = select(Observable).order_by(Observable.created_at.desc())
    count_query = select(func.count(Observable.id))

    if type:
        query = query.where(Observable.type == type)
        count_query = count_query.where(Observable.type == type)

    query = await apply_tenant_access_query(
        request.app,
        query=query,
        resource_type="observable",
        action="list",
        analyst=analyst,
        request=request,
        session=session,
    )
    count_query = await apply_tenant_access_query(
        request.app,
        query=count_query,
        resource_type="observable",
        action="count",
        analyst=analyst,
        request=request,
        session=session,
    )

    total = (await session.execute(count_query)).scalar() or 0
    result = await session.execute(query.offset(offset).limit(limit))
    observables = result.scalars().all()

    return ObservableList(
        observables=[ObservableResponse.model_validate(o) for o in observables],
        total=total,
    )


@router.post("", response_model=ObservableResponse, status_code=201)
async def create_observable(
    data: ObservableCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.OBSERVABLES_MANAGE)),
):
    # Dedup by type + value
    existing = await session.execute(
        select(Observable).where(
            Observable.type == data.type,
            Observable.value == data.value,
        )
    )
    obs = existing.scalar_one_or_none()
    if obs:
        return ObservableResponse.model_validate(obs)

    obs = Observable(
        type=data.type,
        value=data.value,
        source=data.source,
        alert_id=uuid.UUID(data.alert_id) if data.alert_id else None,
        incident_id=uuid.UUID(data.incident_id) if data.incident_id else None,
    )
    await enforce_tenant_access(
        request.app,
        resource=obs,
        resource_type="observable",
        action="create",
        analyst=analyst,
        request=request,
        session=session,
    )
    session.add(obs)
    await session.commit()
    await session.refresh(obs)
    return ObservableResponse.model_validate(obs)


@router.get("/{observable_id}", response_model=ObservableResponse)
async def get_observable(
    observable_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    result = await session.execute(
        select(Observable).where(Observable.id == observable_id)
    )
    obs = result.scalar_one_or_none()
    if not obs:
        raise HTTPException(status_code=404, detail="Observable not found")
    await enforce_tenant_access(
        request.app,
        resource=obs,
        resource_type="observable",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )
    return ObservableResponse.model_validate(obs)


@router.post("/{observable_id}/enrichments", response_model=ObservableResponse)
async def add_enrichment(
    observable_id: uuid.UUID,
    data: EnrichmentCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.OBSERVABLES_MANAGE)),
):
    result = await session.execute(
        select(Observable).where(Observable.id == observable_id)
    )
    obs = result.scalar_one_or_none()
    if not obs:
        raise HTTPException(status_code=404, detail="Observable not found")
    await enforce_tenant_access(
        request.app,
        resource=obs,
        resource_type="observable",
        action="update",
        analyst=analyst,
        request=request,
        session=session,
    )

    enrichment_entry = {
        "source": data.source,
        "data": data.data,
        "malicious": data.malicious,
        "score": data.score,
    }

    current_enrichments = list(obs.enrichments or [])
    current_enrichments.append(enrichment_entry)
    obs.enrichments = current_enrichments
    obs.enrichment_status = "enriched"

    await session.commit()
    await session.refresh(obs)
    return ObservableResponse.model_validate(obs)
