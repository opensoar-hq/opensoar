"""Correlation-ID plumbing for end-to-end log tracing (issue #109).

A single correlation_id threads through the alert -> playbook -> action ->
notification chain so operators can grep one UUID in the logs and see every
event related to a given alert's processing.

The id is stored in a ``contextvars.ContextVar`` so async tasks and Celery
workers isolate their own value — multiple concurrent playbook executions
never see each other's id.  ``CorrelationIdFilter`` pulls the current value
onto every ``LogRecord`` so the stdlib format string ``%(correlation_id)s``
prints the id without callers having to thread it manually.
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

__all__ = [
    "correlation_id_ctx",
    "CorrelationIdFilter",
    "ensure_correlation_id",
    "generate_correlation_id",
    "set_correlation_id",
]


correlation_id_ctx: ContextVar[uuid.UUID | None] = ContextVar(
    "correlation_id_ctx", default=None
)


def generate_correlation_id() -> uuid.UUID:
    """Return a fresh correlation id."""
    return uuid.uuid4()


def set_correlation_id(cid: uuid.UUID | str | None) -> uuid.UUID | None:
    """Set (or clear) the current correlation id and return it as a UUID."""
    if cid is None:
        correlation_id_ctx.set(None)
        return None
    value = cid if isinstance(cid, uuid.UUID) else uuid.UUID(str(cid))
    correlation_id_ctx.set(value)
    return value


def ensure_correlation_id() -> uuid.UUID:
    """Return the current correlation id, generating one if unset."""
    current = correlation_id_ctx.get()
    if current is not None:
        return current
    new_cid = generate_correlation_id()
    correlation_id_ctx.set(new_cid)
    return new_cid


class CorrelationIdFilter(logging.Filter):
    """Inject ``correlation_id`` onto every log record.

    The filter is attached to the root logger at app startup so any library
    that logs via the stdlib picks it up automatically.  When no id is set
    (e.g. at interpreter startup) we emit ``-`` so format strings still
    render cleanly.
    """

    PLACEHOLDER = "-"

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        cid = correlation_id_ctx.get()
        record.correlation_id = str(cid) if cid is not None else self.PLACEHOLDER
        return True
