from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AnalystCreate(BaseModel):
    username: str
    display_name: str
    email: str | None = None
    password: str
    role: str = "analyst"


class AnalystLogin(BaseModel):
    username: str
    password: str


class AnalystResponse(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    email: str | None = None
    is_active: bool
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalystUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    is_active: bool | None = None
    role: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    analyst: AnalystResponse
