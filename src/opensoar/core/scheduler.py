"""Simple interval-based scheduler for recurring playbook triggers.

Multi-instance safety (issue #111): when the scheduler runs in more than one
process (e.g. two API replicas), each instance maintains its own in-memory
schedule and would otherwise fire the same job independently. To avoid
duplicate executions we wrap each scheduled tick in a Redis-backed
``SET NX EX`` lock keyed by ``(job_name, tick_bucket)``. The first instance
to land the key executes; the others skip. The lock TTL is short enough that
a crashed instance cannot stall future runs but long enough to cover a
typical playbook execution.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


# Default TTL for the per-tick Redis lock. Longer than any reasonable playbook
# run, short enough that a crashed holder doesn't stall the next interval.
DEFAULT_LOCK_TTL_SECONDS = 60


class RedisLikeClient(Protocol):
    """Subset of ``redis.asyncio.Redis`` that :class:`DistributedLock` uses."""

    async def set(self, key: str, value: str, *, nx: bool = False, ex: int | None = None) -> Any: ...


class DistributedLock:
    """Thin wrapper around a Redis client that implements ``SET NX EX``.

    The scheduler calls :meth:`acquire` before running a scheduled tick. If
    another instance already holds the key, ``acquire`` returns ``False`` and
    the local scheduler skips execution for that tick.
    """

    def __init__(self, client: RedisLikeClient, key_prefix: str = "opensoar:scheduler:") -> None:
        self._client = client
        self._key_prefix = key_prefix

    def _full_key(self, key: str) -> str:
        if key.startswith(self._key_prefix):
            return key
        return f"{self._key_prefix}{key}"

    async def acquire(self, key: str, *, ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS) -> bool:
        """Attempt to acquire the lock for ``key``.

        Uses ``SET key value NX EX <ttl>`` which returns truthy only when the
        key was created by this call. Any exception from the Redis client is
        treated as "lock unavailable"; the caller then skips this tick rather
        than risk a duplicate execution.
        """
        try:
            result = await self._client.set(
                self._full_key(key),
                "1",
                nx=True,
                ex=max(1, int(ttl_seconds)),
            )
        except Exception:
            logger.exception("scheduler.lock.error key=%s", key)
            return False
        return bool(result)


class Scheduler:
    """Manages recurring jobs that execute on a fixed interval.

    Usage:
        scheduler = Scheduler()
        scheduler.register("poll_elastic", interval_seconds=60, callback=my_async_fn)

        # In your event loop:
        while True:
            await scheduler.tick()
            await asyncio.sleep(1)

    Multi-instance deployments should pass a :class:`DistributedLock`:

        from redis import asyncio as redis_asyncio
        client = redis_asyncio.from_url(settings.redis_url, decode_responses=True)
        scheduler = Scheduler(lock=DistributedLock(client))
    """

    def __init__(
        self,
        lock: DistributedLock | None = None,
        *,
        instance_id: str | None = None,
        lock_ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
    ) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self._lock = lock
        self._instance_id = instance_id or ""
        self._lock_ttl_seconds = lock_ttl_seconds

    def register(
        self,
        name: str,
        *,
        interval_seconds: int,
        callback: Callable,
    ) -> None:
        """Register a recurring job. Replaces any existing job with the same name."""
        self.jobs[name] = {
            "interval": interval_seconds,
            "callback": callback,
            "last_run": 0.0,
            "last_tick_id": None,
        }
        logger.info(f"Scheduler: registered job '{name}' (every {interval_seconds}s)")

    def unregister(self, name: str) -> None:
        """Remove a job by name. No-op if the job doesn't exist."""
        if name in self.jobs:
            del self.jobs[name]
            logger.info(f"Scheduler: unregistered job '{name}'")

    def list_jobs(self) -> list[dict[str, Any]]:
        """Return a summary of all registered jobs."""
        return [
            {
                "name": name,
                "interval": job["interval"],
                "last_run": job["last_run"],
            }
            for name, job in self.jobs.items()
        ]

    def _tick_bucket(self, name: str) -> str:
        """Stable identifier for the current scheduled tick window.

        All instances observing roughly the same wall-clock time will compute
        the same bucket for a given job, so their Redis keys collide and only
        one acquires the lock.
        """
        job = self.jobs[name]
        interval = max(1, int(job["interval"]))
        # Use wall-clock seconds (not monotonic) so concurrent instances on
        # different hosts agree on the bucket.
        bucket = int(time.time()) // interval
        return f"{name}:{bucket}"

    def _lock_key(self, name: str) -> str:
        return self._tick_bucket(name)

    async def tick(self) -> None:
        """Check all jobs and run any that are due.

        If a :class:`DistributedLock` is configured, each due job attempts to
        acquire a per-tick Redis key before executing; instances that lose the
        race skip the execution but still advance ``last_run`` so they don't
        retry in a tight loop within the same interval window.
        """
        now = time.monotonic()
        for name, job in self.jobs.items():
            elapsed = now - job["last_run"]
            if elapsed < job["interval"]:
                continue

            tick_id = self._lock_key(name)

            if self._lock is not None:
                acquired = await self._lock.acquire(
                    tick_id, ttl_seconds=self._lock_ttl_seconds
                )
                if not acquired:
                    # Another instance is (or just was) executing this tick.
                    # Advance our local clock so we don't retry every loop
                    # iteration within the same interval window.
                    job["last_run"] = time.monotonic()
                    job["last_tick_id"] = tick_id
                    logger.debug(
                        "scheduler.skip_locked job=%s tick=%s instance=%s",
                        name,
                        tick_id,
                        self._instance_id,
                    )
                    continue

            try:
                await job["callback"]()
                job["last_run"] = time.monotonic()
                job["last_tick_id"] = tick_id
                logger.debug(f"Scheduler: ran job '{name}'")
            except Exception:
                logger.exception(f"Scheduler: job '{name}' failed")
