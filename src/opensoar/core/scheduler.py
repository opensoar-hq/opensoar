"""Simple interval-based scheduler for recurring playbook triggers."""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


class Scheduler:
    """Manages recurring jobs that execute on a fixed interval.

    Usage:
        scheduler = Scheduler()
        scheduler.register("poll_elastic", interval_seconds=60, callback=my_async_fn)

        # In your event loop:
        while True:
            await scheduler.tick()
            await asyncio.sleep(1)
    """

    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}

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

    async def tick(self) -> None:
        """Check all jobs and run any that are due."""
        now = time.monotonic()
        for name, job in self.jobs.items():
            elapsed = now - job["last_run"]
            if elapsed >= job["interval"]:
                try:
                    await job["callback"]()
                    job["last_run"] = time.monotonic()
                    logger.debug(f"Scheduler: ran job '{name}'")
                except Exception:
                    logger.exception(f"Scheduler: job '{name}' failed")
