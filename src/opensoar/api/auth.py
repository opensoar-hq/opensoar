from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.jwt import create_access_token, require_analyst
from opensoar.auth.rbac import VALID_ANALYST_ROLES
from opensoar.models.analyst import Analyst
from opensoar.plugins import (
    dispatch_audit_event,
    enforce_tenant_access,
    get_analyst_roles,
    get_auth_capabilities,
)
from opensoar.schemas.audit import AuditEvent
from opensoar.schemas.auth import AuthCapabilitiesResponse
from opensoar.schemas.analyst import (
    AnalystCreate,
    AnalystLogin,
    AnalystRegister,
    AnalystRoleResponse,
    AnalystResponse,
    AnalystUpdate,
    MentionableAnalyst,
    PasswordChangeRequest,
    PasswordResetRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _validate_role(role: str) -> str:
    if role not in VALID_ANALYST_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid role. Must be one of: {', '.join(VALID_ANALYST_ROLES)}",
        )
    return role


def _validate_assignable_role(request: Request, role: str) -> str:
    role = _validate_role(role)
    available_roles = {item["id"] for item in get_analyst_roles(request.app)}
    if role not in available_roles:
        raise HTTPException(
            status_code=422,
            detail=f"Role '{role}' is not available in this deployment",
        )
    return role


def _require_local_password(analyst: Analyst) -> str:
    if not analyst.password_hash:
        raise HTTPException(status_code=400, detail="Local password is not configured for this account")
    return analyst.password_hash


async def _assert_not_last_active_admin(
    session: AsyncSession,
    analyst: Analyst,
    update_data: dict[str, object],
) -> None:
    role_after = str(update_data.get("role", analyst.role))
    is_active_after = bool(update_data.get("is_active", analyst.is_active))
    if analyst.role != "admin" or (role_after == "admin" and is_active_after):
        return

    result = await session.execute(
        select(Analyst.id).where(
            Analyst.role == "admin",
            Analyst.is_active.is_(True),
            Analyst.id != analyst.id,
        )
    )
    if result.first() is None:
        raise HTTPException(status_code=400, detail="Cannot remove the last active admin")


@router.get("/capabilities", response_model=AuthCapabilitiesResponse)
async def capabilities(request: Request):
    return AuthCapabilitiesResponse.model_validate(get_auth_capabilities(request.app))


@router.get("/roles", response_model=list[AnalystRoleResponse])
async def list_roles(
    request: Request,
    admin: Analyst = Depends(require_analyst),
):
    if admin.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return [AnalystRoleResponse.model_validate(item) for item in get_analyst_roles(request.app)]


@router.post("/register", response_model=TokenResponse)
async def register(
    request: Request,
    body: AnalystRegister,
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
        role="analyst",
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


@router.post("/change-password")
async def change_password(
    request: Request,
    body: PasswordChangeRequest,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_analyst),
):
    password_hash = _require_local_password(analyst)
    if not _verify_password(body.current_password, password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    analyst.password_hash = _hash_password(body.new_password)
    await session.commit()

    await dispatch_audit_event(
        request.app,
        AuditEvent(
            category="auth",
            action="analyst.password_changed",
            actor_id=analyst.id,
            actor_username=analyst.username,
            target_type="analyst",
            target_id=str(analyst.id),
        ),
    )
    return {"detail": "Password updated"}


# ── Admin endpoints ──────────────────────────────────────────

async def _require_admin(analyst: Analyst = Depends(require_analyst)) -> Analyst:
    if analyst.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return analyst


@router.post("/analysts", response_model=AnalystResponse, status_code=201)
async def create_analyst(
    request: Request,
    body: AnalystCreate,
    session: AsyncSession = Depends(get_db),
    admin: Analyst = Depends(_require_admin),
):
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
        role=_validate_assignable_role(request, body.role),
    )
    session.add(analyst)
    await session.commit()
    await session.refresh(analyst)

    await dispatch_audit_event(
        request.app,
        AuditEvent(
            category="admin",
            action="analyst.created",
            actor_id=admin.id,
            actor_username=admin.username,
            target_type="analyst",
            target_id=str(analyst.id),
            metadata_json={"role": analyst.role},
        ),
    )
    return AnalystResponse.model_validate(analyst)


@router.get("/analysts", response_model=list[AnalystResponse])
async def list_analysts(
    session: AsyncSession = Depends(get_db),
    _admin: Analyst = Depends(_require_admin),
):
    result = await session.execute(select(Analyst).order_by(Analyst.username))
    return [AnalystResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/analysts/mentionable", response_model=list[MentionableAnalyst])
async def list_mentionable_analysts(
    request: Request,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
    analyst: Analyst = Depends(require_analyst),
):
    """Return analysts the caller may ``@mention`` in a comment.

    Results are scoped to active analysts in the caller's tenant — any
    registered ``tenant_access_validators`` plugin decides what "tenant" means.
    Optional ``q`` is a case-insensitive prefix filter on ``username`` or
    ``display_name`` for the autocomplete dropdown.
    """
    query = (
        select(Analyst)
        .where(Analyst.is_active.is_(True))
        .order_by(Analyst.username)
    )
    if q:
        pattern = f"{q.lower()}%"
        query = query.where(
            func.lower(Analyst.username).like(pattern)
            | func.lower(Analyst.display_name).like(pattern)
        )
    # Fetch a small over-size, filter through the tenant hook, then truncate.
    rows = (await session.execute(query.limit(limit * 4))).scalars().all()

    visible: list[Analyst] = []
    for candidate in rows:
        try:
            await enforce_tenant_access(
                request.app,
                resource=candidate,
                resource_type="analyst",
                action="mention",
                analyst=analyst,
                request=request,
                session=session,
            )
        except HTTPException:
            continue
        visible.append(candidate)
        if len(visible) >= limit:
            break
    return [MentionableAnalyst.model_validate(a) for a in visible]


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
    if "role" in update_data:
        update_data["role"] = _validate_assignable_role(request, str(update_data["role"]))
    await _assert_not_last_active_admin(session, analyst, update_data)
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


@router.post("/analysts/{analyst_id}/reset-password")
async def reset_analyst_password(
    analyst_id: str,
    body: PasswordResetRequest,
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

    _require_local_password(analyst)
    analyst.password_hash = _hash_password(body.new_password)
    await session.commit()

    await dispatch_audit_event(
        request.app,
        AuditEvent(
            category="admin",
            action="analyst.password_reset",
            actor_id=admin.id,
            actor_username=admin.username,
            target_type="analyst",
            target_id=str(analyst.id),
        ),
    )
    return {"detail": "Password reset"}
