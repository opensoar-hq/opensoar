"""FastAPI router exposing the Prometheus scrape endpoint at /metrics."""
from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import Response

from opensoar.middleware.metrics import metrics_content_type, render_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Return metrics in Prometheus text exposition format."""
    return Response(content=render_metrics(), media_type=metrics_content_type())
