from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from opensoar.db import Base


class AnalystIdentity(Base):
    __tablename__ = "analyst_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider_type",
            "issuer",
            "subject",
            name="uq_analyst_identities_provider_issuer_subject",
        ),
    )

    analyst_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysts.id", ondelete="CASCADE"),
        index=True,
    )
    provider_type: Mapped[str] = mapped_column(String(50))
    issuer: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    claims_json: Mapped[dict | None] = mapped_column(JSONB)
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
