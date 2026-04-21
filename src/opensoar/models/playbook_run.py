from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
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
    sequence_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    sequence_position: Mapped[int | None] = mapped_column(Integer)
    sequence_total: Mapped[int | None] = mapped_column(Integer)
    # Correlation id inherited from the triggering alert (or freshly minted
    # for manual runs) so every log line during execution can be traced
    # back to the alert that kicked it off (issue #109).
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)

    action_results: Mapped[list["ActionResult"]] = relationship(
        "ActionResult", back_populates="run", lazy="selectin"
    )
