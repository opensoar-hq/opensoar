from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.jwt import create_access_token, require_analyst
from opensoar.models.analyst import Analyst
from opensoar.plugins import dispatch_audit_event, get_auth_capabilities
from opensoar.schemas.audit import AuditEvent
from opensoar.schemas.auth import AuthCapabilitiesResponse
from opensoar.schemas.analyst import (
    AnalystCreate,
    AnalystLogin,
    AnalystResponse,
    AnalystUpdate,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


@router.get("/capabilities", response_model=AuthCapabilitiesResponse)
async def capabilities(request: Request):
    return AuthCapabilitiesResponse.model_validate(get_auth_capabilities(request.app))


@router.post("/register", response_model=TokenResponse)
async def register(
    request: Request,
    body: AnalystCreate,
    session: AsyncSession = Depends(get_db),
):
    if not get_auth_capabilities(request.app)["local_registration_enabled"]:
        raise HTTPException(status_code=403, detail="Local registration is disabled")

    existing = await session.execute(
        select(Analyst).where(Analyst.username == body.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")

    analyst = Analyst(
        username=body.username,
        display_name=body.display_name,
        email=body.email,
        password_hash=_hash_password(body.password),
        role=body.role,
    )
    session.add(analyst)
    await session.commit()
    await session.refresh(analyst)

    await dispatch_audit_event(
        request.app,
        AuditEvent(
            category="auth",
            action="analyst.registered",
            actor_id=analyst.id,
            actor_username=analyst.username,
            target_type="analyst",
            target_id=str(analyst.id),
            metadata_json={"role": analyst.role},
        ),
    )

    token = create_access_token(analyst.id, analyst.username)
    return TokenResponse(
        access_token=token,
        analyst=AnalystResponse.model_validate(analyst),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: AnalystLogin,
    session: AsyncSession = Depends(get_db),
):
    if not get_auth_capabilities(request.app)["local_login_enabled"]:
        raise HTTPException(status_code=403, detail="Local login is disabled")

    result = await session.execute(
        select(Analyst).where(Analyst.username == body.username)
    )
    analyst = result.scalar_one_or_none()
    if not analyst or not analyst.password_hash or not _verify_password(body.password, analyst.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not analyst.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    await dispatch_audit_event(
        request.app,
        AuditEvent(
            category="auth",
            action="analyst.logged_in",
            actor_id=analyst.id,
            actor_username=analyst.username,
            target_type="analyst",
            target_id=str(analyst.id),
        ),
    )

    token = create_access_token(analyst.id, analyst.username)
    return TokenResponse(
        access_token=token,
        analyst=AnalystResponse.model_validate(analyst),
    )


@router.get("/me", response_model=AnalystResponse)
async def get_me(analyst: Analyst = Depends(require_analyst)):
    return AnalystResponse.model_validate(analyst)


# ── Admin endpoints ──────────────────────────────────────────

async def _require_admin(analyst: Analyst = Depends(require_analyst)) -> Analyst:
    if analyst.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return analyst


@router.get("/analysts", response_model=list[AnalystResponse])
async def list_analysts(
    session: AsyncSession = Depends(get_db),
    _admin: Analyst = Depends(_require_admin),
):
    result = await session.execute(select(Analyst).order_by(Analyst.username))
    return [AnalystResponse.model_validate(a) for a in result.scalars().all()]


@router.patch("/analysts/{analyst_id}", response_model=AnalystResponse)
async def update_analyst(
    analyst_id: str,
    body: AnalystUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Analyst = Depends(_require_admin),
):
    import uuid as _uuid

    result = await session.execute(
        select(Analyst).where(Analyst.id == _uuid.UUID(analyst_id))
    )
    analyst = result.scalar_one_or_none()
    if not analyst:
        raise HTTPException(status_code=404, detail="Analyst not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(analyst, field, value)

    await session.commit()
    await session.refresh(analyst)

    await dispatch_audit_event(
        request.app,
        AuditEvent(
            category="admin",
            action="analyst.updated",
            actor_id=admin.id,
            actor_username=admin.username,
            target_type="analyst",
            target_id=str(analyst.id),
            metadata_json={"updated_fields": sorted(update_data.keys())},
        ),
    )
    return AnalystResponse.model_validate(analyst)
