"""Pydantic v2 schemas for AI endpoints."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RecommendedAction = Literal["isolate", "block", "enrich", "escalate", "resolve"]


class AiRecommendation(BaseModel):
    """An analyst-style action recommendation produced by an LLM."""

    action: RecommendedAction
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class RecommendRequest(BaseModel):
    alert_id: str
