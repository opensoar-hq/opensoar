"""add correlation_id to alerts, playbook_runs, action_results

Revision ID: c1b2a3d4e5f6
Revises: b9f28c61a4d3
Create Date: 2026-04-21

Adds a nullable UUID correlation_id column to the three tables in the
alert -> playbook -> action chain so log lines can be stitched together
end-to-end (issue #109).  The id is assigned at ingest and propagated by
the executor; existing rows stay NULL, which the runtime tolerates.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c1b2a3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "b9f28c61a4d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_alerts_correlation_id", "alerts", ["correlation_id"]
    )

    op.add_column(
        "playbook_runs",
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_playbook_runs_correlation_id", "playbook_runs", ["correlation_id"]
    )

    op.add_column(
        "action_results",
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_action_results_correlation_id", "action_results", ["correlation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_action_results_correlation_id", table_name="action_results")
    op.drop_column("action_results", "correlation_id")

    op.drop_index("ix_playbook_runs_correlation_id", table_name="playbook_runs")
    op.drop_column("playbook_runs", "correlation_id")

    op.drop_index("ix_alerts_correlation_id", table_name="alerts")
    op.drop_column("alerts", "correlation_id")
