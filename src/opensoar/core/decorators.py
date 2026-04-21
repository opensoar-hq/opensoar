from __future__ import annotations

import asyncio
import functools
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ActionMeta:
    name: str
    timeout: int = 300
    retries: int = 0
    retry_backoff: float = 1.0
    description: str = ""


@dataclass
class PlaybookMeta:
    name: str
    trigger: str | None = None
    conditions: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    enabled: bool = True
    order: int = 1000
    priority: str = "default"


@dataclass
class RegisteredPlaybook:
    meta: PlaybookMeta
    func: Callable
    module: str


@dataclass
class ExecutionContext:
    run_id: Any
    alert_id: Any | None = None
    session: AsyncSession | None = None
    record_action: Callable | None = None
    # correlation_id plumbed through from alert ingest for log tracing
    # (issue #109).  Matches the alert's correlation_id or is freshly
    # minted for manual runs.
    correlation_id: Any | None = None


_execution_context: ContextVar[ExecutionContext | None] = ContextVar(
    "_execution_context", default=None
)

_PLAYBOOK_REGISTRY: dict[str, RegisteredPlaybook] = {}


def get_playbook_registry() -> dict[str, RegisteredPlaybook]:
    return _PLAYBOOK_REGISTRY


def get_execution_context() -> ExecutionContext | None:
    return _execution_context.get(None)


def set_execution_context(ctx: ExecutionContext | None) -> None:
    _execution_context.set(ctx)


def action(
    name: str | None = None,
    *,
    timeout: int = 300,
    retries: int = 0,
    retry_backoff: float = 1.0,
    description: str = "",
) -> Callable:
    def decorator(func: Callable) -> Callable:
        meta = ActionMeta(
            name=name or func.__name__,
            timeout=timeout,
            retries=retries,
            retry_backoff=retry_backoff,
            description=description,
        )

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = _execution_context.get(None)

            if ctx is None:
                return await func(*args, **kwargs)

            started_at = datetime.now(timezone.utc)
            last_error: str | None = None

            for attempt in range(1, meta.retries + 2):
                try:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs), timeout=meta.timeout
                    )

                    if ctx.record_action:
                        await ctx.record_action(
                            action_name=meta.name,
                            status="success",
                            started_at=started_at,
                            finished_at=datetime.now(timezone.utc),
                            output_data=(
                                result if isinstance(result, dict) else {"result": result}
                            ),
                            attempt=attempt,
                        )
                    return result

                except asyncio.TimeoutError:
                    last_error = f"Timeout after {meta.timeout}s"
                    if attempt <= meta.retries:
                        await asyncio.sleep(meta.retry_backoff**attempt)
                        continue

                    if ctx.record_action:
                        await ctx.record_action(
                            action_name=meta.name,
                            status="failed",
                            started_at=started_at,
                            finished_at=datetime.now(timezone.utc),
                            error=last_error,
                            attempt=attempt,
                        )
                    raise

                except Exception as e:
                    last_error = str(e)
                    if attempt <= meta.retries:
                        await asyncio.sleep(meta.retry_backoff**attempt)
                        continue

                    if ctx.record_action:
                        await ctx.record_action(
                            action_name=meta.name,
                            status="failed",
                            started_at=started_at,
                            finished_at=datetime.now(timezone.utc),
                            error=last_error,
                            attempt=attempt,
                        )
                    raise

            raise RuntimeError(f"Action {meta.name} failed after {meta.retries + 1} attempts")

        wrapper._soar_action = meta
        return wrapper

    return decorator


_VALID_PLAYBOOK_PRIORITIES = ("high", "default", "low")


def playbook(
    trigger: str | None = None,
    *,
    conditions: dict[str, Any] | None = None,
    description: str = "",
    name: str | None = None,
    order: int = 1000,
    priority: str = "default",
) -> Callable:
    if priority not in _VALID_PLAYBOOK_PRIORITIES:
        raise ValueError(
            f"Invalid playbook priority {priority!r}; "
            f"expected one of {_VALID_PLAYBOOK_PRIORITIES}"
        )

    def decorator(func: Callable) -> Callable:
        meta = PlaybookMeta(
            name=name or func.__name__,
            trigger=trigger,
            conditions=conditions or {},
            description=description,
            order=order,
            priority=priority,
        )
        func._soar_playbook = meta

        _PLAYBOOK_REGISTRY[meta.name] = RegisteredPlaybook(
            meta=meta,
            func=func,
            module=func.__module__,
        )

        return func

    return decorator
