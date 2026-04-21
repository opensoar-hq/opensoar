from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_db)):
    try:
        await session.execute(text("SELECT 1"))
        db_status = "healthy"
    # SQLAlchemyError covers every driver-level failure (connection refused,
    # timeout, serialization error, stale connection). OSError catches lower
    # level socket problems that can leak through asyncpg.
    except (SQLAlchemyError, OSError) as e:
        db_status = f"unhealthy: {e}"

    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": "0.1.0",
    }
