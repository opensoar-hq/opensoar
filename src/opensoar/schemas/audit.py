from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    category: str
    action: str
    status: str = "success"
    actor_id: uuid.UUID | None = None
    actor_username: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    metadata_json: dict = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
