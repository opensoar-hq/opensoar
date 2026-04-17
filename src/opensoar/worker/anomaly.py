"""Celery task + beat schedule entry for periodic anomaly detection.

The task itself is a thin wrapper that invokes
:func:`opensoar.ai.anomaly.run_anomaly_detection` against a fresh async
session.  It is safe to schedule via ``celery beat`` or to drive directly from
the in-process ``Scheduler`` utility during local development.
"""
from __future__ import annotations

import asyncio
import logging

from celery.schedules import crontab

from opensoar.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run() -> int:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from opensoar.ai.anomaly import run_anomaly_detection
    from opensoar.config import settings

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with session_factory() as session:
            return await run_anomaly_detection(session)
    finally:
        await engine.dispose()


@celery_app.task(name="opensoar.detect_anomalies")
def detect_anomalies_task() -> dict:
    """Celery entry point — persists anomaly signals for the trailing window."""
    logger.info("running anomaly detection task")
    try:
        inserted = asyncio.run(_run())
    except RuntimeError:
        # We are already inside a running loop (e.g. in-process scheduler) —
        # fall back to a fresh loop on a worker thread.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            inserted = pool.submit(asyncio.run, _run()).result()
    return {"inserted": int(inserted)}


# Run every 15 minutes by default. Beat only picks this up when the worker is
# started with ``celery -A opensoar.worker.celery_app beat``; otherwise the
# in-process Scheduler utility can call ``detect_anomalies_task.delay()`` on a
# matching interval.
celery_app.conf.beat_schedule = {
    **celery_app.conf.get("beat_schedule", {}),
    "opensoar-detect-anomalies": {
        "task": "opensoar.detect_anomalies",
        "schedule": crontab(minute="*/15"),
    },
}
