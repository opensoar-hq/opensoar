from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AvailableAction(BaseModel):
    name: str
    integration: str
    description: str | None = None
    ioc_types: list[str] = []


class ActionExecuteRequest(BaseModel):
    action_name: str
    ioc_type: str
    ioc_value: str
    alert_id: str | None = None


class ActionExecuteResponse(BaseModel):
    action_name: str
    ioc_value: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
