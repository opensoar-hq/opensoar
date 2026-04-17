from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class IncidentTemplateBase(BaseModel):
    name: str
    description: str | None = None
    default_severity: str = "medium"
    default_tags: list[str] = Field(default_factory=list)
    playbook_ids: list[str] = Field(default_factory=list)
    observable_types: list[str] = Field(default_factory=list)


class IncidentTemplateCreate(IncidentTemplateBase):
    tenant_id: uuid.UUID | None = None


class IncidentTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    default_severity: str | None = None
    default_tags: list[str] | None = None
    playbook_ids: list[str] | None = None
    observable_types: list[str] | None = None
    tenant_id: uuid.UUID | None = None


class IncidentTemplateResponse(IncidentTemplateBase):
    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IncidentTemplateList(BaseModel):
    templates: list[IncidentTemplateResponse]
    total: int
