from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.jwt import get_current_analyst
from opensoar.auth.rbac import Permission, require_permission
from opensoar.models.analyst import Analyst
from opensoar.models.incident_template import IncidentTemplate
from opensoar.plugins import apply_tenant_access_query, enforce_tenant_access
from opensoar.schemas.incident_template import (
    IncidentTemplateCreate,
    IncidentTemplateList,
    IncidentTemplateResponse,
    IncidentTemplateUpdate,
)

router = APIRouter(prefix="/incident-templates", tags=["incident-templates"])


@router.get("", response_model=IncidentTemplateList)
async def list_incident_templates(
    request: Request,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    query = select(IncidentTemplate).order_by(IncidentTemplate.created_at.desc())
    count_query = select(func.count(IncidentTemplate.id))

    query = await apply_tenant_access_query(
        request.app,
        query=query,
        resource_type="incident_template",
        action="list",
        analyst=analyst,
        request=request,
        session=session,
    )
    count_query = await apply_tenant_access_query(
        request.app,
        query=count_query,
        resource_type="incident_template",
        action="count",
        analyst=analyst,
        request=request,
        session=session,
    )

    total = (await session.execute(count_query)).scalar() or 0
    result = await session.execute(query.offset(offset).limit(limit))
    templates = result.scalars().all()

    return IncidentTemplateList(
        templates=[IncidentTemplateResponse.model_validate(t) for t in templates],
        total=total,
    )


@router.post("", response_model=IncidentTemplateResponse, status_code=201)
async def create_incident_template(
    data: IncidentTemplateCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.SETTINGS_MANAGE)),
):
    template = IncidentTemplate(
        name=data.name,
        description=data.description,
        default_severity=data.default_severity,
        default_tags=list(data.default_tags),
        playbook_ids=[str(pid) for pid in data.playbook_ids],
        observable_types=list(data.observable_types),
        tenant_id=data.tenant_id,
    )
    await enforce_tenant_access(
        request.app,
        resource=template,
        resource_type="incident_template",
        action="create",
        analyst=analyst,
        request=request,
        session=session,
    )
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return IncidentTemplateResponse.model_validate(template)


@router.get("/{template_id}", response_model=IncidentTemplateResponse)
async def get_incident_template(
    template_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    template = (
        await session.execute(
            select(IncidentTemplate).where(IncidentTemplate.id == template_id)
        )
    ).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Incident template not found")
    await enforce_tenant_access(
        request.app,
        resource=template,
        resource_type="incident_template",
        action="read",
        analyst=analyst,
        request=request,
        session=session,
    )
    return IncidentTemplateResponse.model_validate(template)


@router.patch("/{template_id}", response_model=IncidentTemplateResponse)
async def update_incident_template(
    template_id: uuid.UUID,
    update: IncidentTemplateUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.SETTINGS_MANAGE)),
):
    template = (
        await session.execute(
            select(IncidentTemplate).where(IncidentTemplate.id == template_id)
        )
    ).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Incident template not found")
    await enforce_tenant_access(
        request.app,
        resource=template,
        resource_type="incident_template",
        action="update",
        analyst=analyst,
        request=request,
        session=session,
    )

    update_data = update.model_dump(exclude_unset=True)
    if "playbook_ids" in update_data and update_data["playbook_ids"] is not None:
        update_data["playbook_ids"] = [str(pid) for pid in update_data["playbook_ids"]]
    for field, value in update_data.items():
        setattr(template, field, value)

    await session.commit()
    await session.refresh(template)
    return IncidentTemplateResponse.model_validate(template)


@router.delete("/{template_id}")
async def delete_incident_template(
    template_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_permission(Permission.SETTINGS_MANAGE)),
):
    template = (
        await session.execute(
            select(IncidentTemplate).where(IncidentTemplate.id == template_id)
        )
    ).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Incident template not found")
    await enforce_tenant_access(
        request.app,
        resource=template,
        resource_type="incident_template",
        action="delete",
        analyst=analyst,
        request=request,
        session=session,
    )
    await session.delete(template)
    await session.commit()
    return {"detail": "Incident template deleted"}
