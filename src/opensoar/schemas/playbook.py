from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PlaybookResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    partner: str | None = None
    tenant_id: uuid.UUID | None = None
    execution_order: int
    module_path: str
    function_name: str
    trigger_type: str | None = None
    trigger_config: dict[str, Any]
    enabled: bool
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaybookUpdate(BaseModel):
    enabled: bool | None = None
    partner: str | None = None
    tenant_id: uuid.UUID | None = None


class PlaybookRunRequest(BaseModel):
    alert_id: uuid.UUID | None = None
    input_data: dict[str, Any] | None = None
