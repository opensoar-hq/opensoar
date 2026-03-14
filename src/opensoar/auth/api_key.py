from __future__ import annotations

import hashlib
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.models.api_key import ApiKey

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def generate_api_key() -> tuple[str, str, str]:
    key = f"soar_{secrets.token_urlsafe(32)}"
    prefix = key[:12]
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    return key, prefix, key_hash


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def validate_api_key(
    session: AsyncSession,
    api_key: str | None = Security(api_key_header),
) -> ApiKey | None:
    if api_key is None:
        return None

    key_hash = hash_api_key(api_key)
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    db_key = result.scalar_one_or_none()

    if db_key is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return db_key
