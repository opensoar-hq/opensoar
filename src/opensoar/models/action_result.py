from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from opensoar.db import Base

if TYPE_CHECKING:
    from opensoar.models.playbook_run import PlaybookRun


class ActionResult(Base):
    __tablename__ = "action_results"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("playbook_runs.id"))
    action_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    input_data: Mapped[dict | None] = mapped_column(JSONB)
    output_data: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    # Inherited from the parent PlaybookRun -> Alert chain (issue #109).
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)

    run: Mapped["PlaybookRun"] = relationship("PlaybookRun", back_populates="action_results")
