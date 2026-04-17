from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AnalystRegister(BaseModel):
    username: str
    display_name: str
    email: str | None = None
    password: str
    model_config = {"extra": "forbid"}


class AnalystCreate(BaseModel):
    username: str
    display_name: str
    email: str | None = None
    password: str
    role: str = "analyst"
    model_config = {"extra": "forbid"}


class AnalystLogin(BaseModel):
    username: str
    password: str


class AnalystResponse(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    email: str | None = None
    is_active: bool
    has_local_password: bool
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalystUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    is_active: bool | None = None
    role: str | None = None
    model_config = {"extra": "forbid"}


class AnalystRoleResponse(BaseModel):
    id: str
    label: str


class MentionableAnalyst(BaseModel):
    """Minimal analyst projection used by the comment mention autocomplete."""

    id: uuid.UUID
    username: str
    display_name: str

    model_config = {"from_attributes": True}


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
    model_config = {"extra": "forbid"}


class PasswordResetRequest(BaseModel):
    new_password: str
    model_config = {"extra": "forbid"}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    analyst: AnalystResponse
