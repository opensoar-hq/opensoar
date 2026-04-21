import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from opensoar.db import Base


class Alert(Base):
    __tablename__ = "alerts"

    source: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="new")
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    normalized: Mapped[dict] = mapped_column(JSONB, default=dict)
    # correlation_id is assigned at ingest and propagated through the
    # playbook -> action -> notification chain for end-to-end tracing
    # (issue #109).  Nullable so alerts predating the migration remain valid.
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    source_ip: Mapped[str | None] = mapped_column(String(45))
    dest_ip: Mapped[str | None] = mapped_column(String(45))
    hostname: Mapped[str | None] = mapped_column(String(255))
    rule_name: Mapped[str | None] = mapped_column(String(500))
    iocs: Mapped[dict | None] = mapped_column(JSONB)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    partner: Mapped[str | None] = mapped_column(String(100))
    determination: Mapped[str] = mapped_column(String(30), default="unknown", server_default="unknown")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolve_reason: Mapped[str | None] = mapped_column(String(255))
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysts.id", ondelete="SET NULL")
    )
    assigned_username: Mapped[str | None] = mapped_column(String(100))
    duplicate_count: Mapped[int] = mapped_column(default=1, server_default="1")
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
