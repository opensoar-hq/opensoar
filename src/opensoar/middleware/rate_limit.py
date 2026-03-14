"""Simple in-memory rate limiter for webhook endpoints."""
from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Module-level shared state so tests can reset it
_buckets: dict[str, list[float]] = defaultdict(list)


def reset_rate_limiter() -> None:
    """Clear all rate limiter buckets. Used in tests."""
    _buckets.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter scoped to /api/v1/webhooks/ paths.

    Args:
        app: ASGI application.
        max_requests: Maximum requests per window.
        window_seconds: Time window in seconds.
    """

    def __init__(self, app, *, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def _get_client_key(self, request: Request) -> str:
        """Get a key to identify the client — IP address or API key."""
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"key:{api_key[:12]}"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        client = request.client
        return f"ip:{client.host}" if client else "ip:unknown"

    async def dispatch(self, request: Request, call_next):
        # Only rate-limit webhook endpoints
        if not request.url.path.startswith("/api/v1/webhooks/"):
            return await call_next(request)

        key = self._get_client_key(request)
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Clean old entries
        _buckets[key] = [t for t in _buckets[key] if t > cutoff]

        if len(_buckets[key]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Try again later.",
                    "retry_after": self.window_seconds,
                },
                headers={"Retry-After": str(self.window_seconds)},
            )

        _buckets[key].append(now)
        return await call_next(request)
