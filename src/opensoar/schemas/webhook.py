from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class WebhookResponse(BaseModel):
    alert_id: uuid.UUID
    title: str
    severity: str
    playbooks_triggered: list[str]
    message: str
