"""Tests for rate limiting on webhook endpoints."""
from __future__ import annotations

import asyncio


class TestRateLimit:
    async def test_webhook_rate_limit(self, client):
        """Sending too many requests in a short window should trigger 429."""
        tasks = []
        for i in range(105):
            tasks.append(
                client.post(
                    "/api/v1/webhooks/alerts",
                    json={"rule_name": f"Rate Test {i}", "severity": "low"},
                )
            )
        responses = await asyncio.gather(*tasks)
        status_codes = [r.status_code for r in responses]

        # At least some should be 429
        assert 429 in status_codes, "Expected at least one 429 response from rate limiting"
        # But not all — some should succeed
        assert 200 in status_codes, "Expected at least one 200 response"

    async def test_non_webhook_not_rate_limited(self, client):
        """Non-webhook endpoints should not be rate limited (or have higher limits)."""
        responses = []
        for _ in range(20):
            resp = await client.get("/api/v1/health")
            responses.append(resp.status_code)

        assert all(s == 200 for s in responses)


class TestRateLimitConcurrency:
    """Concurrency safety tests for the token-bucket rate limiter (issue #106)."""

    async def test_lock_is_asyncio_lock(self):
        """The bucket-protecting lock must be an asyncio.Lock, lazily initialized."""
        from opensoar.middleware import rate_limit

        # Before the first async call the lock may be None (lazy init).
        lock = await rate_limit._get_lock()
        assert isinstance(lock, asyncio.Lock)

        # A second call must return the same lock instance — no double init.
        assert await rate_limit._get_lock() is lock

    async def test_concurrent_dispatch_exact_count(self):
        """
        Fire exactly `max_requests` concurrent requests at the middleware. With
        proper locking, all should pass; the (max_requests+1)-th must be 429.

        Without a lock, interleaving between reads of `_buckets[key]` and the
        subsequent append can allow more than `max_requests` to slip through,
        or cause list mutation during iteration to raise/corrupt state.
        """
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        from opensoar.middleware.rate_limit import RateLimitMiddleware, reset_rate_limiter

        reset_rate_limiter()

        async def ok(_: Request) -> JSONResponse:
            # Yield to the loop so coroutines actually interleave.
            await asyncio.sleep(0)
            return JSONResponse({"ok": True})

        app = Starlette(routes=[Route("/api/v1/webhooks/alerts", ok, methods=["POST"])])
        max_requests = 50
        mw = RateLimitMiddleware(app, max_requests=max_requests, window_seconds=60)

        async def call_once() -> int:
            sent: dict = {}

            async def receive():
                return {"type": "http.request", "body": b"{}", "more_body": False}

            async def send(message):
                if message["type"] == "http.response.start":
                    sent["status"] = message["status"]

            scope = {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/api/v1/webhooks/alerts",
                "raw_path": b"/api/v1/webhooks/alerts",
                "query_string": b"",
                "headers": [(b"host", b"test"), (b"x-forwarded-for", b"10.0.0.1")],
                "client": ("10.0.0.1", 1234),
                "server": ("test", 80),
                "root_path": "",
                "app": app,
            }
            await mw(scope, receive, send)
            return sent["status"]

        # Fire max_requests + 1 requests concurrently.
        statuses = await asyncio.gather(*[call_once() for _ in range(max_requests + 1)])
        ok_count = sum(1 for s in statuses if s == 200)
        limited_count = sum(1 for s in statuses if s == 429)

        # Exactly max_requests should succeed, exactly one should be limited.
        assert ok_count == max_requests, (
            f"Expected {max_requests} successes but got {ok_count} (statuses: {statuses})"
        )
        assert limited_count == 1, (
            f"Expected 1 rate-limited response but got {limited_count} (statuses: {statuses})"
        )

    async def test_concurrent_dispatch_no_list_corruption(self):
        """
        Many coroutines hitting the same bucket key simultaneously must not
        corrupt `_buckets[key]` (e.g. lose entries) — after N successful calls
        the bucket length should equal the number of successes.
        """
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        from opensoar.middleware import rate_limit
        from opensoar.middleware.rate_limit import RateLimitMiddleware, reset_rate_limiter

        reset_rate_limiter()

        async def ok(_: Request) -> JSONResponse:
            await asyncio.sleep(0)
            return JSONResponse({"ok": True})

        app = Starlette(routes=[Route("/api/v1/webhooks/alerts", ok, methods=["POST"])])
        max_requests = 200
        mw = RateLimitMiddleware(app, max_requests=max_requests, window_seconds=60)

        async def call_once() -> int:
            sent: dict = {}

            async def receive():
                return {"type": "http.request", "body": b"{}", "more_body": False}

            async def send(message):
                if message["type"] == "http.response.start":
                    sent["status"] = message["status"]

            scope = {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/api/v1/webhooks/alerts",
                "raw_path": b"/api/v1/webhooks/alerts",
                "query_string": b"",
                "headers": [(b"host", b"test"), (b"x-forwarded-for", b"10.0.0.2")],
                "client": ("10.0.0.2", 1234),
                "server": ("test", 80),
                "root_path": "",
                "app": app,
            }
            await mw(scope, receive, send)
            return sent["status"]

        statuses = await asyncio.gather(*[call_once() for _ in range(max_requests)])
        successes = sum(1 for s in statuses if s == 200)

        # All should have succeeded, and the bucket should contain exactly that many timestamps.
        assert successes == max_requests
        bucket = rate_limit._buckets["ip:10.0.0.2"]
        assert len(bucket) == max_requests, (
            f"Bucket length {len(bucket)} != {max_requests} — state was lost under concurrency"
        )
