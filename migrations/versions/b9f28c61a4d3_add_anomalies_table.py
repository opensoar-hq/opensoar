"""add anomalies table

Revision ID: b9f28c61a4d3
Revises: a7c9d2e1b4f6
Create Date: 2026-04-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "b9f28c61a4d3"
down_revision: Union[str, Sequence[str], None] = "569afa72352c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "anomalies",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("partner", sa.String(100), nullable=True),
        sa.Column("rule_name", sa.String(500), nullable=True),
        sa.Column("source_ip", sa.String(45), nullable=True),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("details", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_anomalies"),
    )
    op.create_index("ix_anomalies_kind", "anomalies", ["kind"])
    op.create_index("ix_anomalies_partner", "anomalies", ["partner"])
    op.create_index("ix_anomalies_rule_name", "anomalies", ["rule_name"])
    op.create_index("ix_anomalies_created_at", "anomalies", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_anomalies_created_at", table_name="anomalies")
    op.drop_index("ix_anomalies_rule_name", table_name="anomalies")
    op.drop_index("ix_anomalies_partner", table_name="anomalies")
    op.drop_index("ix_anomalies_kind", table_name="anomalies")
    op.drop_table("anomalies")
