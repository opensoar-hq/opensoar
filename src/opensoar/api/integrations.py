from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.models.integration import IntegrationInstance
from opensoar.schemas.integration import (
    IntegrationCreate,
    IntegrationResponse,
    IntegrationUpdate,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(IntegrationInstance).order_by(IntegrationInstance.name)
    )
    integrations = result.scalars().all()
    return [IntegrationResponse.model_validate(i) for i in integrations]


@router.post("", response_model=IntegrationResponse, status_code=201)
async def create_integration(
    data: IntegrationCreate,
    session: AsyncSession = Depends(get_db),
):
    integration = IntegrationInstance(
        integration_type=data.integration_type,
        name=data.name,
        config=data.config,
        enabled=data.enabled,
    )
    session.add(integration)
    await session.commit()
    await session.refresh(integration)
    return IntegrationResponse.model_validate(integration)


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(IntegrationInstance).where(IntegrationInstance.id == integration_id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return IntegrationResponse.model_validate(integration)


@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: uuid.UUID,
    update: IntegrationUpdate,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(IntegrationInstance).where(IntegrationInstance.id == integration_id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(integration, field, value)

    await session.commit()
    await session.refresh(integration)
    return IntegrationResponse.model_validate(integration)


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(IntegrationInstance).where(IntegrationInstance.id == integration_id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    await session.delete(integration)
    await session.commit()
    return {"detail": "Integration deleted"}
