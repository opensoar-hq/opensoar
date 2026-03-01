from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.config import settings
from opensoar.models.analyst import Analyst

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(analyst_id: uuid.UUID, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(analyst_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_analyst(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> Analyst | None:
    """Returns the current analyst if a valid token is provided, None otherwise."""
    if credentials is None:
        return None

    payload = decode_token(credentials.credentials)
    analyst_id = payload.get("sub")
    if not analyst_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await session.execute(
        select(Analyst).where(Analyst.id == uuid.UUID(analyst_id))
    )
    analyst = result.scalar_one_or_none()
    if analyst is None or not analyst.is_active:
        raise HTTPException(status_code=401, detail="Analyst not found or inactive")

    return analyst


async def require_analyst(
    analyst: Analyst | None = Depends(get_current_analyst),
) -> Analyst:
    """Requires a valid authenticated analyst."""
    if analyst is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return analyst
