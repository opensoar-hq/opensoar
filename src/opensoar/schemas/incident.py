from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class IncidentCreate(BaseModel):
    title: str
    description: str | None = None
    severity: str | None = None
    tags: list[str] | None = None
    template_id: uuid.UUID | None = None


class IncidentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    status: str | None = None
    assigned_to: str | None = None
    tags: list[str] | None = None


class IncidentResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    severity: str
    status: str
    assigned_to: uuid.UUID | None = None
    assigned_username: str | None = None
    tags: list[str] | None = None
    alert_count: int = 0
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IncidentList(BaseModel):
    incidents: list[IncidentResponse]
    total: int


class LinkAlertRequest(BaseModel):
    alert_id: str
