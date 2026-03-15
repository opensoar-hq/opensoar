from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ObservableCreate(BaseModel):
    type: str
    value: str
    source: str | None = None
    alert_id: str | None = None
    incident_id: str | None = None


class ObservableResponse(BaseModel):
    id: uuid.UUID
    type: str
    value: str
    source: str | None = None
    enrichment_status: str
    enrichments: list[dict[str, Any]] | None = None
    tags: list[str] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ObservableList(BaseModel):
    observables: list[ObservableResponse]
    total: int


class EnrichmentCreate(BaseModel):
    source: str
    data: dict[str, Any]
    malicious: bool = False
    score: float | None = None
