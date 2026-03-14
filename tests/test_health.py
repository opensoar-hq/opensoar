"""Tests for health check endpoint and structured logging."""
from __future__ import annotations


class TestHealthEndpoint:
    async def test_health_ok(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "healthy"
        assert "version" in data
