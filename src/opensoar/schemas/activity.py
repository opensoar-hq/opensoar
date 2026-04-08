from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ActivityResponse(BaseModel):
    id: uuid.UUID
    alert_id: uuid.UUID | None = None
    incident_id: uuid.UUID | None = None
    analyst_id: uuid.UUID | None = None
    analyst_username: str | None = None
    action: str
    detail: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ActivityList(BaseModel):
    activities: list[ActivityResponse]
    total: int


class CommentCreate(BaseModel):
    text: str


class CommentUpdate(BaseModel):
    text: str
