from __future__ import annotations

from pydantic import BaseModel


class AuthProviderCapability(BaseModel):
    id: str
    name: str
    type: str
    login_url: str | None = None


class AuthCapabilitiesResponse(BaseModel):
    local_login_enabled: bool
    local_registration_enabled: bool
    providers: list[AuthProviderCapability]
