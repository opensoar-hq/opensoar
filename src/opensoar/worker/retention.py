"""Celery task + beat schedule for periodic retention enforcement."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery.schedules import crontab

from opensoar.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _execute_purge(dry_run: bool) -> dict[str, Any]:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from opensoar.config import settings
    from opensoar.retention.service import run_retention_purge

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as session:
            return await run_retention_purge(
                session, dry_run=dry_run, actor_username="celery-beat"
            )
    finally:
        await engine.dispose()


@celery_app.task(name="opensoar.purge_retention", bind=True, max_retries=2)
def purge_retention_task(self, dry_run: bool = False) -> dict[str, Any]:
    """Periodic task that purges records past retention thresholds."""
    logger.info("Running retention purge (dry_run=%s)", dry_run)
    try:
        result = _run_async(_execute_purge(dry_run))
        logger.info("Retention purge result: %s", result)
        return result
    except Exception as exc:  # pragma: no cover - retry path
        logger.exception("Retention purge failed")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


# Run daily at 03:15 UTC.
celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    "opensoar-retention-purge": {
        "task": "opensoar.purge_retention",
        "schedule": crontab(hour=3, minute=15),
        "args": (False,),
    },
}
