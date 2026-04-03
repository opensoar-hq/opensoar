from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.api_key import generate_api_key
from opensoar.auth.jwt import require_analyst
from opensoar.models.analyst import Analyst
from opensoar.models.api_key import ApiKey
from opensoar.plugins import dispatch_audit_event
from opensoar.schemas.audit import AuditEvent

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    is_active: bool
    last_used_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Only returned on creation — includes the full key (shown once)."""
    key: str = ""


async def _require_admin(analyst: Analyst = Depends(require_analyst)) -> Analyst:
    if analyst.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return analyst


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    session: AsyncSession = Depends(get_db),
    _admin: Analyst = Depends(_require_admin),
):
    result = await session.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return [ApiKeyResponse.model_validate(k) for k in result.scalars().all()]


@router.post("", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    request: Request,
    body: ApiKeyCreate,
    session: AsyncSession = Depends(get_db),
    admin: Analyst = Depends(_require_admin),
):
    key, prefix, key_hash = generate_api_key()
    api_key = ApiKey(name=body.name, key_hash=key_hash, prefix=prefix)
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    await dispatch_audit_event(
        request.app,
        AuditEvent(
            category="admin",
            action="api_key.created",
            actor_id=admin.id,
            actor_username=admin.username,
            target_type="api_key",
            target_id=str(api_key.id),
            metadata_json={"name": api_key.name, "prefix": api_key.prefix},
        ),
    )

    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        key=key,
    )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Analyst = Depends(_require_admin),
):
    result = await session.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    await session.commit()

    await dispatch_audit_event(
        request.app,
        AuditEvent(
            category="admin",
            action="api_key.revoked",
            actor_id=admin.id,
            actor_username=admin.username,
            target_type="api_key",
            target_id=str(api_key.id),
            metadata_json={"name": api_key.name, "prefix": api_key.prefix},
        ),
    )
    return {"detail": "API key revoked"}
