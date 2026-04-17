from __future__ import annotations

import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from opensoar.db import Base


class IncidentTemplate(Base):
    """Reusable incident template applied at incident creation.

    The template captures the defaults a responder would otherwise have to
    re-enter for each incident of a given type (severity, tags, IOC extraction
    targets) and lists playbooks that should auto-run when an incident is
    created from the template.  Templates can be global (``tenant_id`` NULL)
    or tenant-scoped; enforcement goes through the standard tenant-access
    validator chain in :mod:`opensoar.plugins`.
    """

    __tablename__ = "incident_templates"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    default_severity: Mapped[str] = mapped_column(String(20), default="medium")
    default_tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    playbook_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    observable_types: Mapped[list[str]] = mapped_column(JSONB, default=list)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
