from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: uuid.UUID
    source: str
    source_id: str | None = None
    title: str
    description: str | None = None
    severity: str
    status: str
    source_ip: str | None = None
    dest_ip: str | None = None
    hostname: str | None = None
    rule_name: str | None = None
    iocs: dict[str, Any] | None = None
    tags: list[str] | None = None
    partner: str | None = None
    determination: str = "unknown"
    assigned_to: uuid.UUID | None = None
    assigned_username: str | None = None
    duplicate_count: int = 1
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertDetailResponse(AlertResponse):
    raw_payload: dict[str, Any] = {}
    normalized: dict[str, Any] = {}
    resolved_at: datetime | None = None
    resolve_reason: str | None = None


class AlertUpdate(BaseModel):
    status: str | None = None
    severity: str | None = None
    resolve_reason: str | None = None
    determination: str | None = None
    partner: str | None = None
    tags: list[str] | None = None
    assigned_to: str | None = None


class AlertList(BaseModel):
    alerts: list[AlertResponse]
    total: int


class BulkAlertUpdate(BaseModel):
    alert_ids: list[uuid.UUID]
    action: str  # "resolve", "assign", "change_severity"
    resolve_reason: str | None = None
    determination: str | None = None
    assigned_to: str | None = None
    severity: str | None = None


class BulkOperationResult(BaseModel):
    updated: int
    failed: int
    errors: list[str] = []
