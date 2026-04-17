"""Semantic alert deduplication endpoint (issue #81).

POST /ai/deduplicate accepts an ``alert_id`` and returns near-duplicate
candidate alerts ranked by cosine similarity of their embedding vectors.
Uses the shared Redis-backed enrichment cache (``integrations/cache.py``)
keyed by alert id so repeated requests avoid a round-trip to the provider.

Kept in its own module so it doesn't collide with the parallel PRs that
also touch ``opensoar.api.ai`` (anomaly detection, recommendations).
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.ai.embeddings import (
    EmbeddingClient,
    cosine_similarity,
    get_embedding_client,
)
from opensoar.api.deps import get_db
from opensoar.auth.rbac import Permission, require_permission
from opensoar.config import settings
from opensoar.integrations.cache import EnrichmentCache, get_default_cache
from opensoar.models.alert import Alert
from opensoar.models.analyst import Analyst

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

EMBEDDING_CACHE_KEY_PREFIX = "opensoar:ai_embedding:"
# Cap how many other alerts we compare against per request. Keeps latency
# predictable without requiring pgvector / ANN index.
DEDUP_CORPUS_LIMIT = 500


class DeduplicateRequest(BaseModel):
    alert_id: str
    threshold: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Override AI_DEDUP_THRESHOLD for this request.",
    )
    limit: int = Field(default=10, ge=1, le=50)


def _cache_key(alert_id: str) -> str:
    return f"{EMBEDDING_CACHE_KEY_PREFIX}{alert_id}"


def _alert_text(alert: Alert) -> str:
    """Build a representative text payload for embedding a single alert."""
    parts = [
        f"Title: {alert.title or ''}",
        f"Severity: {alert.severity or ''}",
        f"Rule: {alert.rule_name or ''}",
        f"Source: {alert.source or ''}",
        f"Hostname: {alert.hostname or ''}",
        f"Source IP: {alert.source_ip or ''}",
        f"Destination IP: {alert.dest_ip or ''}",
    ]
    if alert.description:
        parts.append(f"Description: {alert.description}")
    if alert.tags:
        parts.append(f"Tags: {', '.join(alert.tags)}")
    if alert.iocs:
        parts.append(f"IOCs: {json.dumps(alert.iocs, default=str)}")
    return "\n".join(p for p in parts if p.split(": ", 1)[-1])


async def _get_or_compute_embedding(
    alert: Alert,
    client: EmbeddingClient,
    cache: EnrichmentCache,
) -> list[float]:
    """Fetch a cached embedding for ``alert`` or compute and persist one."""
    key = _cache_key(str(alert.id))
    cached_raw = await cache.backend.get(key)
    if cached_raw is not None:
        try:
            payload = json.loads(cached_raw)
            vector = payload.get("vector")
            if isinstance(vector, list) and vector:
                return [float(v) for v in vector]
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("ai_embedding.cache_decode_failed alert_id=%s", alert.id)

    text = _alert_text(alert)
    response = await client.embed(text)
    payload = {"vector": response.vector, "model": response.model}
    try:
        encoded = json.dumps(payload)
    except (TypeError, ValueError):
        logger.warning("ai_embedding.cache_encode_failed alert_id=%s", alert.id)
        return list(response.vector)

    ttl = getattr(settings, "ai_embedding_cache_ttl", 7 * 24 * 3600)
    await cache.backend.set(key, encoded, ttl_seconds=int(ttl))
    return list(response.vector)


@router.post("/deduplicate")
async def deduplicate_alert(
    body: DeduplicateRequest,
    session: AsyncSession = Depends(get_db),
    _analyst: Analyst = Depends(require_permission(Permission.AI_USE)),
) -> dict[str, Any]:
    """Return near-duplicate candidate alerts for the requested alert id.

    Candidates are ranked by cosine similarity of their embeddings.
    Returns 503 if no embedding provider is configured.
    """
    client = get_embedding_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Semantic deduplication is not configured. "
                "Set AI_EMBEDDING_PROVIDER along with OPENAI_API_KEY or OLLAMA_URL."
            ),
        )

    try:
        alert_uuid = uuid.UUID(body.alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert_id")

    target = (
        await session.execute(select(Alert).where(Alert.id == alert_uuid))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    cache = get_default_cache()
    threshold = (
        body.threshold
        if body.threshold is not None
        else float(getattr(settings, "ai_dedup_threshold", 0.85))
    )

    target_vector = await _get_or_compute_embedding(target, client, cache)

    # Pull the most recent candidate corpus. Skip the target itself.
    corpus_query = (
        select(Alert)
        .where(Alert.id != target.id)
        .order_by(Alert.created_at.desc())
        .limit(DEDUP_CORPUS_LIMIT)
    )
    corpus = (await session.execute(corpus_query)).scalars().all()

    scored: list[dict[str, Any]] = []
    for candidate in corpus:
        try:
            cand_vector = await _get_or_compute_embedding(candidate, client, cache)
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "ai_dedup.embedding_failed alert_id=%s", candidate.id
            )
            continue
        score = cosine_similarity(target_vector, cand_vector)
        if score >= threshold:
            scored.append(
                {
                    "alert_id": str(candidate.id),
                    "similarity": round(score, 4),
                    "title": candidate.title,
                    "severity": candidate.severity,
                }
            )

    scored.sort(key=lambda r: r["similarity"], reverse=True)
    scored = scored[: body.limit]

    return {
        "alert_id": str(target.id),
        "threshold": threshold,
        "provider": client.provider,
        "model": client.model,
        "candidates": scored,
    }
