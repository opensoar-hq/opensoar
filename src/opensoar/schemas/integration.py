from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class IntegrationCreate(BaseModel):
    integration_type: str
    name: str
    config: dict[str, Any] = {}
    enabled: bool = True


class IntegrationUpdate(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    enabled: bool | None = None


class IntegrationResponse(BaseModel):
    id: uuid.UUID
    integration_type: str
    name: str
    enabled: bool
    health_status: str | None = None
    last_health_check: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
