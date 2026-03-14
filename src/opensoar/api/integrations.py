from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])

# Registry of known integration connector classes
_INTEGRATION_CONNECTORS: dict[str, type] = {}


def _discover_connectors() -> None:
    """Lazy-load built-in integration connector classes."""
    if _INTEGRATION_CONNECTORS:
        return
    try:
        from opensoar.integrations.elastic.connector import ElasticIntegration

        _INTEGRATION_CONNECTORS["elastic"] = ElasticIntegration
    except ImportError:
        pass
    try:
        from opensoar.integrations.virustotal.connector import VirusTotalIntegration

        _INTEGRATION_CONNECTORS["virustotal"] = VirusTotalIntegration
    except ImportError:
        pass
    try:
        from opensoar.integrations.abuseipdb.connector import AbuseIPDBIntegration

        _INTEGRATION_CONNECTORS["abuseipdb"] = AbuseIPDBIntegration
    except ImportError:
        pass
    try:
        from opensoar.integrations.slack.connector import SlackIntegration

        _INTEGRATION_CONNECTORS["slack"] = SlackIntegration
    except ImportError:
        pass


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


@router.post("/{integration_id}/health")
async def check_integration_health(
    integration_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Run a health check on an integration and persist the result."""
    result = await session.execute(
        select(IntegrationInstance).where(IntegrationInstance.id == integration_id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    _discover_connectors()
    connector_cls = _INTEGRATION_CONNECTORS.get(integration.integration_type)

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
