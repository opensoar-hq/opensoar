"""Queue routing helpers for Celery clustered workers (issue #85).

Three logical priority classes map 1:1 to Celery queues:

    ``high``     — latency-sensitive playbooks (e.g. auto-containment).
    ``default``  — general-purpose playbooks and unknown priorities.
    ``low``      — background work (observable enrichment, backfills).

A @playbook is tagged with a priority via the decorator's ``priority`` kwarg
(default ``"default"``). At enqueue time, ``execute_playbook_task`` looks up
the registered playbook's priority and routes the task onto the matching
queue. Callers can override with an explicit ``priority=`` kwarg on
``delay()``.

Operators run two Celery worker processes: one consuming ``high,default`` and
one consuming ``low``. Either can scale independently without starving the
other.
"""
from __future__ import annotations

QUEUE_HIGH = "high"
QUEUE_DEFAULT = "default"
QUEUE_LOW = "low"

VALID_PRIORITIES: frozenset[str] = frozenset({QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW})

# Ordering used when a sequence task spans multiple playbooks with differing
# priorities — the most urgent wins so nothing lingers behind a low-priority
# peer in the same batch.
_PRIORITY_RANK = {QUEUE_HIGH: 0, QUEUE_DEFAULT: 1, QUEUE_LOW: 2}


def queue_for_priority(priority: str | None) -> str:
    """Map a priority string to its queue name.

    Unknown or ``None`` values fall back to ``default`` — routing must never
    raise at enqueue time.
    """
    if priority in VALID_PRIORITIES:
        return priority  # type: ignore[return-value]
    return QUEUE_DEFAULT


def queue_for_playbook(playbook_name: str) -> str:
    """Look up the queue for a registered playbook name.

    If the playbook is unknown (not yet imported on the enqueuing side, or a
    typo) we fall back to ``default`` rather than raising — the worker will
    still surface the real "playbook not found" error when it runs.
    """
    # Local import to avoid a circular dependency with the decorators module
    # at worker-module import time.
    from opensoar.core.decorators import get_playbook_registry

    registered = get_playbook_registry().get(playbook_name)
    if registered is None:
        return QUEUE_DEFAULT
    return queue_for_priority(registered.meta.priority)


def highest_priority_queue(playbook_names: list[str]) -> str:
    """Return the most-urgent queue across a list of playbook names.

    Used by ``execute_playbook_sequence_task`` so a batch containing a
    ``high`` playbook does not get starved behind ``low``-queue work.
    """
    if not playbook_names:
        return QUEUE_DEFAULT

    best = QUEUE_DEFAULT
    best_rank = _PRIORITY_RANK[best]
    for name in playbook_names:
        q = queue_for_playbook(name)
        rank = _PRIORITY_RANK.get(q, _PRIORITY_RANK[QUEUE_DEFAULT])
        if rank < best_rank:
            best = q
            best_rank = rank
    return best
