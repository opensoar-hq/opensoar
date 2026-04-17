"""add retention archived_at columns

Revision ID: b8d4e6f12a77
Revises: a7c9d2e1b4f6
Create Date: 2026-04-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8d4e6f12a77"
down_revision: Union[str, Sequence[str], None] = "a7c9d2e1b4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add archived_at soft-delete columns for retention policies."""
    op.add_column(
        "alerts",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "activities",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_alerts_archived_at", "alerts", ["archived_at"], unique=False
    )
    op.create_index(
        "ix_incidents_archived_at", "incidents", ["archived_at"], unique=False
    )
    op.create_index(
        "ix_activities_archived_at", "activities", ["archived_at"], unique=False
    )


def downgrade() -> None:
    """Drop retention archived_at columns."""
    op.drop_index("ix_activities_archived_at", table_name="activities")
    op.drop_index("ix_incidents_archived_at", table_name="incidents")
    op.drop_index("ix_alerts_archived_at", table_name="alerts")
    op.drop_column("activities", "archived_at")
    op.drop_column("incidents", "archived_at")
    op.drop_column("alerts", "archived_at")
