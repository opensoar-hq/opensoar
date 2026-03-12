"""add partner, rename closed to resolved, determination defaults

Revision ID: b5e1a3c8d2f7
Revises: f3b7c2d91e4a
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b5e1a3c8d2f7"
down_revision: str | None = "f3b7c2d91e4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add partner column
    op.add_column("alerts", sa.Column("partner", sa.String(100), nullable=True))

    # Rename closed_at -> resolved_at, close_reason -> resolve_reason
    op.alter_column("alerts", "closed_at", new_column_name="resolved_at")
    op.alter_column("alerts", "close_reason", new_column_name="resolve_reason")

    # Backfill nulls first, then set NOT NULL + default
    op.execute("UPDATE alerts SET determination = 'unknown' WHERE determination IS NULL")
    op.alter_column(
        "alerts", "determination",
        server_default="unknown",
        nullable=False,
    )

    # Rename status 'closed' -> 'resolved'
    op.execute("UPDATE alerts SET status = 'resolved' WHERE status = 'closed'")

    # Migrate old determination values to new ones
    op.execute("UPDATE alerts SET determination = 'malicious' WHERE determination = 'true_positive'")
    op.execute("UPDATE alerts SET determination = 'benign' WHERE determination IN ('false_positive', 'benign')")


def downgrade() -> None:
    op.execute("UPDATE alerts SET status = 'closed' WHERE status = 'resolved'")
    op.alter_column("alerts", "resolved_at", new_column_name="closed_at")
    op.alter_column("alerts", "resolve_reason", new_column_name="close_reason")
    op.alter_column("alerts", "determination", server_default=None, nullable=True)
    op.drop_column("alerts", "partner")
