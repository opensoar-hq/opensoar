from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from opensoar.db import Base


class IntegrationInstance(Base):
    __tablename__ = "integration_instances"

    integration_type: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    partner: Mapped[str | None] = mapped_column(String(100))
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health_status: Mapped[str | None] = mapped_column(String(20))
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
