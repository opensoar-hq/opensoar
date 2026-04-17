from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from opensoar.db import Base


class Activity(Base):
    """Audit trail entry for alert and incident activity streams."""

    __tablename__ = "activities"

    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    analyst_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysts.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(50))
    # e.g. "status_change", "severity_change", "comment", "playbook_triggered",
    #      "ioc_enriched", "assigned", "closed", "retention_purge"
    detail: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    analyst_username: Mapped[str | None] = mapped_column(String(100))
    mentions: Mapped[list[str] | None] = mapped_column(JSONB)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
