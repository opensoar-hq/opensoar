"""add incident activity stream

Revision ID: f1a2b3c4d5e6
Revises: e6f7a8b9c0d1
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("activities", "alert_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column(
        "activities",
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_activities_incident_id_incidents"),
        "activities",
        "incidents",
        ["incident_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_activities_incident_id"),
        "activities",
        ["incident_id"],
        unique=False,
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM activities WHERE alert_id IS NULL"))
    op.drop_index(op.f("ix_activities_incident_id"), table_name="activities")
    op.drop_constraint(op.f("fk_activities_incident_id_incidents"), "activities", type_="foreignkey")
    op.drop_column("activities", "incident_id")
    op.alter_column("activities", "alert_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
