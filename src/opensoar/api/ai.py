"""AI-powered alert analysis endpoints."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.ai.client import LLMClient
from opensoar.ai.prompts import (
    build_auto_resolve_prompt,
    build_correlation_prompt,
    build_playbook_prompt,
    build_recommendation_prompt,
    build_summarize_prompt,
    build_triage_prompt,
)
from opensoar.api.deps import get_db
from opensoar.auth.jwt import require_analyst
from opensoar.auth.rbac import Permission, require_permission
from opensoar.config import settings
from opensoar.models.alert import Alert
from opensoar.models.analyst import Analyst
from opensoar.models.observable import Observable
from opensoar.schemas.ai import AiRecommendation, RecommendRequest

ALLOWED_ACTIONS = {"isolate", "block", "enrich", "escalate", "resolve"}
SIMILAR_ALERT_LIMIT = 5

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


def get_llm_client() -> LLMClient | None:
    """Create an LLM client from environment config, or None if not configured."""
    if settings.anthropic_api_key:
        return LLMClient(
            provider="anthropic",
            api_key=settings.anthropic_api_key,
            model=settings.llm_model or "claude-sonnet-4-6",
        )
    if settings.openai_api_key:
        return LLMClient(
            provider="openai",
            api_key=settings.openai_api_key,
            model=settings.llm_model or "gpt-4o",
        )
    if settings.ollama_url:
        return LLMClient(
            provider="ollama",
            base_url=settings.ollama_url,
            model=settings.llm_model or "llama3",
        )
    return None


class SummarizeRequest(BaseModel):
    alert_id: str


class TriageRequest(BaseModel):
    alert_id: str


@router.post("/summarize")
async def summarize_alert(
    body: SummarizeRequest,
    session: AsyncSession = Depends(get_db),
    _analyst: Analyst = Depends(require_analyst),
):
    """Generate a natural language summary of an alert using an LLM."""
    client = get_llm_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="AI features not configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or OLLAMA_URL.",
        )

    result = await session.execute(
        select(Alert).where(Alert.id == uuid.UUID(body.alert_id))
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert_data = {
        "title": alert.title,
        "severity": alert.severity,
        "description": alert.description,
        "source_ip": alert.source_ip,
        "dest_ip": alert.dest_ip,
        "hostname": alert.hostname,
        "rule_name": alert.rule_name,
        "iocs": alert.iocs,
        "tags": alert.tags,
        "source": alert.source,
    }

    prompt = build_summarize_prompt(alert_data)
    response = await client.complete(
        prompt,
        system="You are a senior SOC analyst. Provide concise, actionable alert summaries.",
    )

    return {
        "summary": response.content,
        "model": response.model,
        "usage": response.usage,
    }


@router.post("/triage")
async def triage_alert(
    body: TriageRequest,
    session: AsyncSession = Depends(get_db),
    _analyst: Analyst = Depends(require_analyst),
):
    """Suggest severity and determination for an alert using an LLM."""
    client = get_llm_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="AI features not configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or OLLAMA_URL.",
        )

    result = await session.execute(
        select(Alert).where(Alert.id == uuid.UUID(body.alert_id))
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert_data = {
        "title": alert.title,
        "severity": alert.severity,
        "status": alert.status,
        "description": alert.description,
        "source_ip": alert.source_ip,
        "dest_ip": alert.dest_ip,
        "hostname": alert.hostname,
        "rule_name": alert.rule_name,
        "iocs": alert.iocs,
        "tags": alert.tags,
        "source": alert.source,
        "raw_payload": alert.raw_payload,
    }

    prompt = build_triage_prompt(alert_data)
    response = await client.complete(
        prompt,
        system="You are a senior SOC analyst specializing in alert triage. Respond with JSON only.",
        temperature=0.1,
    )

    # Parse LLM response as JSON
    try:
        triage = json.loads(response.content)
    except json.JSONDecodeError:
        triage = {
            "severity": "unknown",
            "determination": "unknown",
            "confidence": 0.0,
            "reasoning": response.content,
        }

    return {
        "severity": triage.get("severity", "unknown"),
        "determination": triage.get("determination", "unknown"),
        "confidence": triage.get("confidence", 0.0),
        "reasoning": triage.get("reasoning", ""),
        "model": response.model,
        "usage": response.usage,
    }


class GeneratePlaybookRequest(BaseModel):
    description: str


@router.post("/generate-playbook")
async def generate_playbook(
    body: GeneratePlaybookRequest,
    _analyst: Analyst = Depends(require_analyst),
):
    """Generate a Python playbook from a natural language description."""
    client = get_llm_client()
    if client is None:
        raise HTTPException(status_code=503, detail="AI features not configured.")

    prompt = build_playbook_prompt(body.description)
    response = await client.complete(
        prompt,
        system="You are an expert Python developer specializing in security automation. Write clean, production-ready async Python code.",
        max_tokens=2048,
        temperature=0.2,
    )

    # Strip markdown fences if the LLM wraps them
    code = response.content.strip()
    if code.startswith("```python"):
        code = code[len("```python"):].strip()
    if code.startswith("```"):
        code = code[3:].strip()
    if code.endswith("```"):
        code = code[:-3].strip()

    return {
        "code": code,
        "model": response.model,
        "usage": response.usage,
    }


class AutoResolveRequest(BaseModel):
    alert_ids: list[str]


@router.post("/auto-resolve")
async def auto_resolve(
    body: AutoResolveRequest,
    session: AsyncSession = Depends(get_db),
    _analyst: Analyst = Depends(require_analyst),
):
    """Evaluate alerts for automatic resolution as benign."""
    client = get_llm_client()
    if client is None:
        raise HTTPException(status_code=503, detail="AI features not configured.")

    # Fetch alerts
    alerts_data = []
    for aid in body.alert_ids:
        result = await session.execute(
            select(Alert).where(Alert.id == uuid.UUID(aid))
        )
        alert = result.scalar_one_or_none()
        if alert:
            alerts_data.append({
                "id": str(alert.id),
                "title": alert.title,
                "severity": alert.severity,
                "source_ip": alert.source_ip,
                "hostname": alert.hostname,
                "rule_name": alert.rule_name,
                "tags": alert.tags,
                "description": alert.description,
            })

    if not alerts_data:
        return {"results": []}

    prompt = build_auto_resolve_prompt(alerts_data)
    response = await client.complete(
        prompt,
        system="You are a conservative SOC analyst. Only recommend auto-resolve for clearly benign alerts.",
        temperature=0.1,
    )

    try:
        parsed = json.loads(response.content)
        if isinstance(parsed, list):
            results = parsed
        elif isinstance(parsed, dict) and "results" in parsed:
            results = parsed["results"]
        elif isinstance(parsed, dict):
            # Single result for a single alert
            results = [parsed]
        else:
            results = []
    except json.JSONDecodeError:
        results = [
            {"alert_index": i, "should_resolve": False, "confidence": 0.0, "reasoning": "Failed to parse LLM response"}
            for i in range(len(alerts_data))
        ]

    # Map alert_index back to alert_id
    for r in results:
        if isinstance(r, dict):
            idx = r.get("alert_index", 0)
            if isinstance(idx, int) and 0 <= idx < len(alerts_data):
                r["alert_id"] = alerts_data[idx]["id"]

    return {
        "results": results,
        "model": response.model,
    }


class CorrelateRequest(BaseModel):
    alert_ids: list[str]


@router.post("/correlate")
async def correlate_alerts(
    body: CorrelateRequest,
    session: AsyncSession = Depends(get_db),
    _analyst: Analyst = Depends(require_analyst),
):
    """Use LLM reasoning to group related alerts into potential incidents."""
    client = get_llm_client()
    if client is None:
        raise HTTPException(status_code=503, detail="AI features not configured.")

    alerts_data = []
    for aid in body.alert_ids:
        result = await session.execute(
            select(Alert).where(Alert.id == uuid.UUID(aid))
        )
        alert = result.scalar_one_or_none()
        if alert:
            alerts_data.append({
                "id": str(alert.id),
                "title": alert.title,
                "severity": alert.severity,
                "source_ip": alert.source_ip,
                "dest_ip": alert.dest_ip,
                "hostname": alert.hostname,
                "rule_name": alert.rule_name,
                "tags": alert.tags,
            })

    if len(alerts_data) < 2:
        return {"groups": []}

    prompt = build_correlation_prompt(alerts_data)
    response = await client.complete(
        prompt,
        system="You are a threat intelligence analyst specializing in attack chain identification.",
        temperature=0.2,
    )

    try:
        result_data = json.loads(response.content)
    except json.JSONDecodeError:
        result_data = {"groups": []}

    return {
        "groups": result_data.get("groups", []),
        "model": response.model,
    }


def _normalize_confidence(raw: Any) -> float:
    """Parse + clamp an LLM-reported confidence into [0.0, 1.0].

    Accepts floats, ints, and percentage-style numbers. Values in (2, 100]
    are treated as percentages and scaled by /100. Values just above 1.0
    (e.g. 1.4) are treated as overconfident floats and clamped to 1.0 —
    that is much more likely than a 1.4% confidence.
    """
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if value > 2.0 and value <= 100.0:
        value = value / 100.0
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


@router.post("/recommend", response_model=AiRecommendation)
async def recommend_action(
    body: RecommendRequest,
    session: AsyncSession = Depends(get_db),
    _analyst: Analyst = Depends(require_permission(Permission.AI_USE)),
) -> AiRecommendation:
    """Ask the LLM what a seasoned analyst would do for this alert."""
    client = get_llm_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="AI features not configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or OLLAMA_URL.",
        )

    try:
        alert_uuid = uuid.UUID(body.alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert_id") from None

    result = await session.execute(select(Alert).where(Alert.id == alert_uuid))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Linked observables + their enrichments
    obs_result = await session.execute(
        select(Observable).where(Observable.alert_id == alert_uuid)
    )
    observables = [
        {
            "type": obs.type,
            "value": obs.value,
            "source": obs.source,
            "enrichment_status": obs.enrichment_status,
            "enrichments": obs.enrichments or [],
            "tags": obs.tags or [],
        }
        for obs in obs_result.scalars().all()
    ]

    # Similar past alerts by shared source_ip (top-N, newest first, excluding self)
    similar: list[dict[str, Any]] = []
    if alert.source_ip:
        similar_result = await session.execute(
            select(Alert)
            .where(Alert.source_ip == alert.source_ip, Alert.id != alert_uuid)
            .order_by(Alert.created_at.desc())
            .limit(SIMILAR_ALERT_LIMIT)
        )
        similar = [
            {
                "id": str(s.id),
                "title": s.title,
                "severity": s.severity,
                "status": s.status,
                "determination": s.determination,
                "rule_name": s.rule_name,
            }
            for s in similar_result.scalars().all()
        ]

    alert_data = {
        "title": alert.title,
        "severity": alert.severity,
        "status": alert.status,
        "description": alert.description,
        "source_ip": alert.source_ip,
        "dest_ip": alert.dest_ip,
        "hostname": alert.hostname,
        "rule_name": alert.rule_name,
        "iocs": alert.iocs,
        "tags": alert.tags,
        "source": alert.source,
    }

    prompt = build_recommendation_prompt(alert_data, observables, similar)
    response = await client.complete(
        prompt,
        system=(
            "You are a senior SOC analyst. Recommend the single best next action. "
            "Respond with JSON only."
        ),
        temperature=0.1,
    )

    content = (response.content or "").strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:].strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("recommend: LLM returned non-JSON output, falling back to escalate")
        return AiRecommendation(
            action="escalate",
            confidence=0.0,
            reasoning=f"Could not parse LLM response: {response.content[:500]}",
        )

    raw_action = parsed.get("action") if isinstance(parsed, dict) else None
    action = raw_action if raw_action in ALLOWED_ACTIONS else "escalate"
    confidence = _normalize_confidence(parsed.get("confidence", 0.0) if isinstance(parsed, dict) else 0.0)
    reasoning = ""
    if isinstance(parsed, dict):
        reasoning = str(parsed.get("reasoning", "")).strip()
    if not reasoning:
        reasoning = "No reasoning provided by the model."
    if raw_action not in ALLOWED_ACTIONS:
        reasoning = (
            f"Model returned unsupported action '{raw_action}'; defaulting to escalate. "
            + reasoning
        )

    return AiRecommendation(action=action, confidence=confidence, reasoning=reasoning)
