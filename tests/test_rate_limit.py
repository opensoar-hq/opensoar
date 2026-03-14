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
