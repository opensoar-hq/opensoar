"""Prometheus metrics — counters, histograms, middleware, and /metrics endpoint.

Exposes an isolated ``CollectorRegistry`` so the application can reset metrics
between tests without disturbing any global default registry shared with
other libraries.
"""
from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# The /metrics endpoint itself is excluded from the HTTP request counter so
# scraping does not inflate its own metric.
_METRICS_PATH = "/metrics"

# Dedicated registry keeps OpenSOAR metrics separate from any library defaults.
registry: CollectorRegistry = CollectorRegistry()

http_requests_total: Counter = Counter(
    "opensoar_http_requests_total",
    "Total HTTP requests handled by the OpenSOAR API.",
    ("method", "path", "status"),
    registry=registry,
)

alerts_ingested_total: Counter = Counter(
    "opensoar_alerts_ingested_total",
    "Total alerts ingested via webhooks grouped by source.",
    ("source",),
    registry=registry,
)

playbook_runs_total: Counter = Counter(
    "opensoar_playbook_runs_total",
    "Total playbook executions grouped by playbook name and status.",
    ("playbook", "status"),
    registry=registry,
)

playbook_run_duration_seconds: Histogram = Histogram(
    "opensoar_playbook_run_duration_seconds",
    "Duration of playbook executions in seconds.",
    ("playbook",),
    registry=registry,
)


def reset_metrics() -> None:
    """Clear collected samples from every OpenSOAR metric.

    Used by tests so counter/histogram state does not leak between cases.
    """
    for metric in (
        http_requests_total,
        alerts_ingested_total,
        playbook_runs_total,
        playbook_run_duration_seconds,
    ):
        # prometheus_client exposes ``_metrics`` as the labelled-child store.
        metric._metrics.clear()  # noqa: SLF001 — intentional reset for tests


def record_http_request(method: str, path: str, status: int) -> None:
    """Increment the HTTP request counter."""
    http_requests_total.labels(method=method, path=path, status=str(status)).inc()


def record_alert_ingested(source: str) -> None:
    """Increment the alert ingest counter for a given source."""
    alerts_ingested_total.labels(source=source).inc()


def record_playbook_run(playbook_name: str, status: str, duration_seconds: float) -> None:
    """Record a completed playbook run (counter + histogram)."""
    playbook_runs_total.labels(playbook=playbook_name, status=status).inc()
    playbook_run_duration_seconds.labels(playbook=playbook_name).observe(duration_seconds)


def render_metrics() -> bytes:
    """Render the current registry in Prometheus text exposition format."""
    return generate_latest(registry)


def metrics_content_type() -> str:
    """Return the Prometheus exposition content-type header value."""
    return CONTENT_TYPE_LATEST


class MetricsMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that records per-request HTTP metrics.

    The ``/metrics`` path itself is skipped so scraping does not inflate the
    counter. Request duration is not tracked as a separate histogram yet —
    only the count is exposed, which is sufficient for basic rate and error
    monitoring.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path == _METRICS_PATH:
            return await call_next(request)

        start = time.monotonic()
        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            # Always record, even for exceptions (status defaults to 500).
            duration = time.monotonic() - start
            _ = duration  # reserved for future per-request histogram
            record_http_request(
                method=request.method,
                path=request.url.path,
                status=status_code,
            )
