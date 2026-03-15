from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from opensoar.db import Base


class Incident(Base):
    __tablename__ = "incidents"

    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="open")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysts.id", ondelete="SET NULL")
    )
    assigned_username: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
