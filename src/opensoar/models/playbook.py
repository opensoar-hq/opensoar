from sqlalchemy import String, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from opensoar.db import Base


class PlaybookDefinition(Base):
    __tablename__ = "playbook_definitions"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    partner: Mapped[str | None] = mapped_column(String(100))
    module_path: Mapped[str] = mapped_column(String(500))
    function_name: Mapped[str] = mapped_column(String(255))
    trigger_type: Mapped[str | None] = mapped_column(String(50))
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
