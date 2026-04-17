"""Pydantic response schemas for anomaly records."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AnomalyResponse(BaseModel):
    id: uuid.UUID
    kind: str
    partner: str | None = None
    rule_name: str | None = None
    source_ip: str | None = None
    score: float
    details: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnomalyList(BaseModel):
    anomalies: list[AnomalyResponse]
    total: int
