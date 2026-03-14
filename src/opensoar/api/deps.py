from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.db import async_session


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session() as session:
        yield session
