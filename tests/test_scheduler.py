"""Tests for the scheduler — recurring playbook triggers."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from opensoar.core.scheduler import DistributedLock, Scheduler


class TestScheduler:
    def test_register_interval_job(self):
        """Should register a job with an interval."""
        scheduler = Scheduler()
        scheduler.register("poll_elastic", interval_seconds=60, callback=AsyncMock())
        assert "poll_elastic" in scheduler.jobs
        assert scheduler.jobs["poll_elastic"]["interval"] == 60

    def test_register_duplicate_replaces(self):
        """Registering the same job name should replace the old one."""
        scheduler = Scheduler()
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        scheduler.register("job", interval_seconds=30, callback=cb1)
        scheduler.register("job", interval_seconds=60, callback=cb2)
        assert scheduler.jobs["job"]["interval"] == 60
        assert scheduler.jobs["job"]["callback"] is cb2

    def test_unregister_job(self):
        """Should remove a registered job."""
        scheduler = Scheduler()
        scheduler.register("temp_job", interval_seconds=10, callback=AsyncMock())
        scheduler.unregister("temp_job")
        assert "temp_job" not in scheduler.jobs

    def test_unregister_nonexistent_no_error(self):
        """Unregistering a job that doesn't exist should not raise."""
        scheduler = Scheduler()
        scheduler.unregister("nonexistent")  # Should not raise

    def test_list_jobs(self):
        """Should return all registered job names and intervals."""
        scheduler = Scheduler()
        scheduler.register("job_a", interval_seconds=30, callback=AsyncMock())
        scheduler.register("job_b", interval_seconds=120, callback=AsyncMock())
        jobs = scheduler.list_jobs()
        assert len(jobs) == 2
        names = [j["name"] for j in jobs]
        assert "job_a" in names
        assert "job_b" in names

    async def test_tick_calls_due_callbacks(self):
        """tick() should call callbacks that are due."""
        scheduler = Scheduler()
        cb = AsyncMock()
        scheduler.register("tick_test", interval_seconds=0, callback=cb)
        await scheduler.tick()
        cb.assert_awaited_once()

    async def test_tick_skips_not_due(self):
        """tick() should skip callbacks that are not yet due."""
        scheduler = Scheduler()
        cb = AsyncMock()
        scheduler.register("not_due", interval_seconds=9999, callback=cb)
        # Set last_run to now so it's not due
        import time
        scheduler.jobs["not_due"]["last_run"] = time.monotonic()
        await scheduler.tick()
        cb.assert_not_awaited()


class FakeRedisBackend:
    """Minimal fake of redis.asyncio client for SET NX EX semantics.

    Shared across instances to simulate a single Redis server seen by
    multiple scheduler processes.
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key, value, *, nx=False, ex=None):  # noqa: ARG002
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        self.store.pop(key, None)
        return 1


class TestDistributedLock:
    """DistributedLock wraps a Redis-style client with SET NX EX semantics."""

    async def test_acquire_returns_true_when_unheld(self):
        client = FakeRedisBackend()
        lock = DistributedLock(client)
        assert await lock.acquire("job:tick-1", ttl_seconds=60) is True

    async def test_acquire_returns_false_when_held(self):
        client = FakeRedisBackend()
        lock = DistributedLock(client)
        assert await lock.acquire("job:tick-1", ttl_seconds=60) is True
        # Second attempt from same process or another process: denied.
        assert await lock.acquire("job:tick-1", ttl_seconds=60) is False

    async def test_acquire_different_keys_independent(self):
        client = FakeRedisBackend()
        lock = DistributedLock(client)
        assert await lock.acquire("job:tick-1", ttl_seconds=60) is True
        assert await lock.acquire("job:tick-2", ttl_seconds=60) is True


class TestDistributedScheduler:
    """When a lock is configured, only one instance runs each scheduled tick."""

    async def test_single_instance_runs_with_lock(self):
        """A lone scheduler should still fire jobs normally when a lock is set."""
        client = FakeRedisBackend()
        cb = AsyncMock()
        scheduler = Scheduler(lock=DistributedLock(client))
        scheduler.register("lonely", interval_seconds=0, callback=cb)
        await scheduler.tick()
        cb.assert_awaited_once()

    async def test_two_instances_race_only_one_executes(self):
        """Two schedulers sharing a Redis lock must not double-execute."""
        client = FakeRedisBackend()  # shared "Redis"
        cb_a = AsyncMock()
        cb_b = AsyncMock()

        sched_a = Scheduler(lock=DistributedLock(client), instance_id="a")
        sched_b = Scheduler(lock=DistributedLock(client), instance_id="b")
        # Both instances registered the same logical job.
        sched_a.register("sync_job", interval_seconds=0, callback=cb_a)
        sched_b.register("sync_job", interval_seconds=0, callback=cb_b)

        # Run both ticks concurrently — simulates two API instances racing.
        await asyncio.gather(sched_a.tick(), sched_b.tick())

        total_calls = cb_a.await_count + cb_b.await_count
        assert total_calls == 1, (
            f"Expected exactly one execution across instances, got {total_calls}"
        )

    async def test_next_tick_after_interval_runs_again(self):
        """The lock key is per scheduled tick, not permanent — next tick runs."""
        client = FakeRedisBackend()
        cb = AsyncMock()
        scheduler = Scheduler(lock=DistributedLock(client))
        scheduler.register("periodic", interval_seconds=0, callback=cb)

        await scheduler.tick()
        # Simulate the prior bucket's key expiring (as Redis TTL would) so the
        # next scheduled tick starts fresh.
        client.store.clear()
        scheduler.jobs["periodic"]["last_run"] = 0.0
        await scheduler.tick()

        assert cb.await_count == 2

    async def test_skipped_execution_advances_last_run(self):
        """When lock is denied, the job should not rerun on the next tick
        within the same interval window (avoids tight-loop retries)."""
        client = FakeRedisBackend()
        cb = AsyncMock()
        lock = DistributedLock(client)
        scheduler = Scheduler(lock=lock, instance_id="b")
        scheduler.register("held", interval_seconds=60, callback=cb)

        # Pre-acquire the lock via the same DistributedLock so prefixes match.
        assert await lock.acquire(scheduler._lock_key("held"), ttl_seconds=60)

        await scheduler.tick()
        cb.assert_not_awaited()
        # A second immediate tick must not run either — last_run was advanced.
        await scheduler.tick()
        cb.assert_not_awaited()
