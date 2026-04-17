import uuid

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from opensoar.db import Base


class PlaybookDefinition(Base):
    __tablename__ = "playbook_definitions"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    partner: Mapped[str | None] = mapped_column(String(100))
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    module_path: Mapped[str] = mapped_column(String(500))
    function_name: Mapped[str] = mapped_column(String(255))
    trigger_type: Mapped[str | None] = mapped_column(String(50))
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    execution_order: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000")
    version: Mapped[int] = mapped_column(Integer, default=1)
