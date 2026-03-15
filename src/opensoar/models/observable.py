from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from opensoar.db import Base


class Observable(Base):
    __tablename__ = "observables"

    type: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(1000))
    source: Mapped[str | None] = mapped_column(String(100))
    enrichment_status: Mapped[str] = mapped_column(String(20), default="pending")
    enrichments: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("alerts.id", ondelete="SET NULL")
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL")
    )
