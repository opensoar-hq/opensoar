from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class ActivityResponse(BaseModel):
    id: uuid.UUID
    alert_id: uuid.UUID | None = None
    incident_id: uuid.UUID | None = None
    analyst_id: uuid.UUID | None = None
    analyst_username: str | None = None
    action: str
    detail: str | None = None
    metadata_json: dict[str, Any] | None = None
    mentions: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("mentions", mode="before")
    @classmethod
    def _coerce_mentions(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return value


class ActivityList(BaseModel):
    activities: list[ActivityResponse]
    total: int


class CommentCreate(BaseModel):
    text: str


class CommentUpdate(BaseModel):
    text: str


class TimelineEvent(BaseModel):
    """A single entry in an aggregated incident timeline.

    `source` distinguishes whether the event came from an alert activity or an
    incident activity so the UI can render per-source filters and badges.
    """

    id: uuid.UUID
    source: str  # "incident" | "alert"
    action: str
    detail: str | None = None
    created_at: datetime
    updated_at: datetime
    analyst_id: uuid.UUID | None = None
    analyst_username: str | None = None
    alert_id: uuid.UUID | None = None
    incident_id: uuid.UUID | None = None
    metadata_json: dict[str, Any] | None = None
    mentions: list[str] = []

    model_config = {"from_attributes": True}


class TimelineList(BaseModel):
    events: list[TimelineEvent]
    total: int
