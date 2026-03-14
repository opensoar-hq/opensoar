"""Tests for the scheduler — recurring playbook triggers."""
from __future__ import annotations

from unittest.mock import AsyncMock

from opensoar.core.scheduler import Scheduler


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
