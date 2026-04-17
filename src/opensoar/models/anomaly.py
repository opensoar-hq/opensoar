"""Model for anomalies produced by the AI anomaly detector."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from opensoar.db import Base


class Anomaly(Base):
    """An anomaly signal produced by the rolling baseline analyser.

    Each row represents a single heuristic firing for a
    ``(partner, rule_name, source_ip)`` tuple on a given detection run.
    """

    __tablename__ = "anomalies"

    kind: Mapped[str] = mapped_column(String(50), index=True)
    # "count_spike" | "first_seen_ip" | "new_severity"
    partner: Mapped[str | None] = mapped_column(String(100), index=True)
    rule_name: Mapped[str | None] = mapped_column(String(500), index=True)
    source_ip: Mapped[str | None] = mapped_column(String(45))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    # Override created_at to add an index — anomaly listings are paginated by
    # recency and this keeps /ai/anomalies fast as the table grows.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )
