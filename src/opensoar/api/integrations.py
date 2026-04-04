from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.rbac import Permission, require_permission
from opensoar.integrations.loader import IntegrationLoader
from opensoar.models.analyst import Analyst
from opensoar.models.integration import IntegrationInstance
from opensoar.plugins import apply_tenant_access_query, enforce_tenant_access
from opensoar.schemas.integration import (
    IntegrationCreate,
    IntegrationResponse,
    IntegrationUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])

# Singleton loader — discovered once, reused
_loader = IntegrationLoader()


def _get_loader() -> IntegrationLoader:
    if not _loader.available_types():
        _loader.discover_builtin()
    return _loader


@router.get("/types")
async def list_available_types():
    """Return all available integration types with metadata."""
    loader = _get_loader()
    return loader.available_types_detail()


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.INTEGRATIONS_READ)),
):
    query = select(IntegrationInstance).order_by(IntegrationInstance.name)
    query = await apply_tenant_access_query(
        request.app,
        query=query,
        resource_type="integration",
        action="list",
        analyst=analyst,
        request=request,
        session=session,
    )
    result = await session.execute(query)
    integrations = result.scalars().all()
    return [IntegrationResponse.model_validate(i) for i in integrations]


@router.post("", response_model=IntegrationResponse, status_code=201)
async def create_integration(
    data: IntegrationCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
):
    integration = IntegrationInstance(
        integration_type=data.integration_type,
        name=data.name,
        partner=data.partner,
        config=data.config,
        enabled=data.enabled,
    )
    await enforce_tenant_access(
        request.app,
        resource=integration,
        resource_type="integration",
        action="create",
        analyst=analyst,
        request=request,
        session=session,
    )
    session.add(integration)
    await session.commit()
    await session.refresh(integration)
    return IntegrationResponse.model_validate(integration)


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.INTEGRATIONS_READ)),
):
    result = await session.execute(
        select(IntegrationInstance).where(IntegrationInstance.id == integration_id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    await enforce_tenant_access(
        request.app,
        resource=integration,
        resource_type="integration",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )
    return IntegrationResponse.model_validate(integration)


@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: uuid.UUID,
    update: IntegrationUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
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
    await enforce_tenant_access(
        request.app,
        resource=integration,
        resource_type="integration",
        action="update",
        analyst=analyst,
        request=request,
        session=session,
    )

    await session.commit()
    await session.refresh(integration)
    return IntegrationResponse.model_validate(integration)


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
):
    result = await session.execute(
        select(IntegrationInstance).where(IntegrationInstance.id == integration_id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    await enforce_tenant_access(
        request.app,
        resource=integration,
        resource_type="integration",
        action="delete",
        analyst=analyst,
        request=request,
        session=session,
    )

    await session.delete(integration)
    await session.commit()
    return {"detail": "Integration deleted"}


@router.post("/{integration_id}/health")
async def check_integration_health(
    integration_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
):
    """Run a health check on an integration and persist the result."""
    result = await session.execute(
        select(IntegrationInstance).where(IntegrationInstance.id == integration_id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    await enforce_tenant_access(
        request.app,
        resource=integration,
        resource_type="integration",
        action="health",
        analyst=analyst,
        request=request,
        session=session,
    )

    loader = _get_loader()
    connector_cls = loader.get_connector(integration.integration_type)

    if connector_cls is None:
        health_status = "unhealthy"
        message = f"Integration type '{integration.integration_type}' not supported"
        details = None
    else:
        try:
            connector = connector_cls(integration.config)
            await connector.connect()
            check = await connector.health_check()
            health_status = "healthy" if check.healthy else "unhealthy"
            message = check.message
            details = check.details
            await connector.disconnect()
        except Exception as e:
            health_status = "unhealthy"
            message = str(e)
            details = None
            logger.warning(f"Health check failed for {integration.name}: {e}")

    integration.health_status = health_status
    integration.last_health_check = datetime.now(timezone.utc)
    await session.commit()

    return {
        "healthy": health_status == "healthy",
        "message": message,
        "details": details,
    }
