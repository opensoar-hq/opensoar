from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from opensoar.db import Base

if TYPE_CHECKING:
    from opensoar.models.action_result import ActionResult


class PlaybookRun(Base):
    __tablename__ = "playbook_runs"

    playbook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("playbook_definitions.id"))
    alert_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("alerts.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSONB)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))

    action_results: Mapped[list["ActionResult"]] = relationship(
        "ActionResult", back_populates="run", lazy="selectin"
    )
