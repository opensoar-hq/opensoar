from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ActionResultResponse(BaseModel):
    id: uuid.UUID
    action_name: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    error: str | None = None
    attempt: int
    correlation_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class PlaybookRunResponse(BaseModel):
    id: uuid.UUID
    playbook_id: uuid.UUID
    alert_id: uuid.UUID | None = None
    sequence_id: uuid.UUID | None = None
    sequence_position: int | None = None
    sequence_total: int | None = None
    correlation_id: uuid.UUID | None = None
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    action_results: list[ActionResultResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaybookRunList(BaseModel):
    runs: list[PlaybookRunResponse]
    total: int
