from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable

from celery import Task

from opensoar.worker.celery_app import celery_app
from opensoar.worker.routing import (
    QUEUE_DEFAULT,
    highest_priority_queue,
    queue_for_playbook,
    queue_for_priority,
)

logger = logging.getLogger(__name__)


class _PlaybookRoutedTask(Task):
    """Celery Task that picks its queue from the playbook's priority.

    The playbook name is always the first positional arg (either a string for
    ``execute_playbook`` or a list[str] for ``execute_playbook_sequence``).
    Callers may override the chosen queue with ``priority="high"`` etc on
    ``delay()``. The override is stripped before the task runs — workers
    never see it.
    """

    abstract = True

    def _resolve_queue(self, args: tuple, priority_override: str | None) -> str:
        if priority_override is not None:
            return queue_for_priority(priority_override)
        if not args:
            return QUEUE_DEFAULT
        first = args[0]
        if isinstance(first, str):
            return queue_for_playbook(first)
        if isinstance(first, list):
            return highest_priority_queue([n for n in first if isinstance(n, str)])
        return QUEUE_DEFAULT

    def delay(self, *args, **kwargs):
        priority = kwargs.pop("priority", None)
        queue = self._resolve_queue(args, priority)
        return self.apply_async(args=args, kwargs=kwargs, queue=queue)


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


async def _execute(playbook_name: str, alert_id: str | None) -> dict:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from opensoar.config import settings
    from opensoar.core.decorators import get_playbook_registry
    from opensoar.core.executor import PlaybookExecutor
    from opensoar.core.registry import PlaybookRegistry

    registry = PlaybookRegistry(settings.playbook_directories)
    registry.discover()

    pb_registry = get_playbook_registry()
    pb = pb_registry.get(playbook_name)
    if not pb:
        raise ValueError(f"Playbook '{playbook_name}' not found in registry")

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        await registry.sync_to_db(session)

        executor = PlaybookExecutor(session)
        run = await executor.execute(
            pb,
            alert_id=uuid.UUID(alert_id) if alert_id else None,
        )

        result = {
            "run_id": str(run.id),
            "status": run.status,
            "error": run.error,
        }

    await engine.dispose()
    return result


async def _execute_sequence(
    playbook_names: list[str],
    alert_id: str | None,
    *,
    session_factory: Callable | None = None,
) -> dict:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from opensoar.config import settings
    from opensoar.core.decorators import get_playbook_registry
    from opensoar.core.executor import PlaybookExecutor
    from opensoar.core.registry import PlaybookRegistry

    registry = PlaybookRegistry(settings.playbook_directories)
    registry.discover()

    pb_registry = get_playbook_registry()
    sequence_id = uuid.uuid4()
    engine = None
    if session_factory is None:
        engine = create_async_engine(settings.database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    results = []
    async with session_factory() as session:
        await registry.sync_to_db(session)
        executor = PlaybookExecutor(session)

        for playbook_name in playbook_names:
            position = len(results) + 1
            pb = pb_registry.get(playbook_name)
            if not pb:
                raise ValueError(f"Playbook '{playbook_name}' not found in registry")

            run = await executor.execute(
                pb,
                alert_id=uuid.UUID(alert_id) if alert_id else None,
                sequence_id=sequence_id,
                sequence_position=position,
                sequence_total=len(playbook_names),
            )
            results.append(
                {
                    "playbook_name": playbook_name,
                    "run_id": str(run.id),
                    "sequence_id": str(sequence_id),
                    "sequence_position": position,
                    "sequence_total": len(playbook_names),
                    "status": run.status,
                    "error": run.error,
                }
            )

    if engine is not None:
        await engine.dispose()
    return {
        "alert_id": alert_id,
        "results": results,
    }


@celery_app.task(
    name="opensoar.execute_playbook",
    bind=True,
    max_retries=3,
    base=_PlaybookRoutedTask,
)
def execute_playbook_task(self, playbook_name: str, alert_id: str | None = None) -> dict:
    logger.info(f"Executing playbook '{playbook_name}' (alert_id={alert_id})")

    try:
        result = _run_async(_execute(playbook_name, alert_id))
        logger.info(f"Playbook '{playbook_name}' finished: {result}")
        return result
    # Celery task retry path — playbooks execute arbitrary user code so any
    # subclass of ``Exception`` is a legitimate retry trigger. ``BaseException``
    # (SystemExit, KeyboardInterrupt) still propagates to shut the worker down.
    except Exception as e:  # noqa: BLE001 - retry path for arbitrary user code
        logger.exception(f"Playbook '{playbook_name}' failed")
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery_app.task(
    name="opensoar.execute_playbook_sequence",
    bind=True,
    max_retries=3,
    base=_PlaybookRoutedTask,
)
def execute_playbook_sequence_task(self, playbook_names: list[str], alert_id: str | None = None) -> dict:
    logger.info(f"Executing playbook sequence {playbook_names} (alert_id={alert_id})")

    try:
        result = _run_async(_execute_sequence(playbook_names, alert_id))
        logger.info(f"Playbook sequence finished: {result}")
        return result
    # Celery task retry path — sequences run arbitrary user code. See the
    # single-playbook task above for the same rationale.
    except Exception as e:  # noqa: BLE001 - retry path for arbitrary user code
        logger.exception("Playbook sequence failed")
        raise self.retry(exc=e, countdown=2**self.request.retries)
