"""add sequence metadata to playbook runs

Revision ID: e6f7a8b9c0d1
Revises: d3a4b5c6e7f8
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d3a4b5c6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "playbook_runs",
        sa.Column("sequence_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "playbook_runs",
        sa.Column("sequence_position", sa.Integer(), nullable=True),
    )
    op.add_column(
        "playbook_runs",
        sa.Column("sequence_total", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_playbook_runs_sequence_id"),
        "playbook_runs",
        ["sequence_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_playbook_runs_sequence_id"), table_name="playbook_runs")
    op.drop_column("playbook_runs", "sequence_total")
    op.drop_column("playbook_runs", "sequence_position")
    op.drop_column("playbook_runs", "sequence_id")
