from __future__ import annotations

import uuid

from pydantic import BaseModel


class WebhookResponse(BaseModel):
    alert_id: uuid.UUID
    correlation_id: uuid.UUID | None = None
    title: str
    severity: str
    playbooks_triggered: list[str]
    message: str
