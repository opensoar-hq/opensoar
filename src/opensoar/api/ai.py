"""AI-powered alert analysis endpoints."""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.ai.client import LLMClient
from opensoar.ai.prompts import build_summarize_prompt, build_triage_prompt
from opensoar.api.deps import get_db
from opensoar.auth.jwt import require_analyst
from opensoar.config import settings
from opensoar.models.alert import Alert
from opensoar.models.analyst import Analyst

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


def get_llm_client() -> LLMClient | None:
    """Create an LLM client from environment config, or None if not configured."""
    if settings.anthropic_api_key:
        return LLMClient(
            provider="anthropic",
            api_key=settings.anthropic_api_key,
            model=settings.llm_model or "claude-sonnet-4-20250514",
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
