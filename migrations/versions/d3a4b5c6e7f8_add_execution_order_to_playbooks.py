"""add execution order to playbooks

Revision ID: d3a4b5c6e7f8
Revises: 9d1a2c3b4e55
Create Date: 2026-04-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3a4b5c6e7f8"
down_revision: Union[str, Sequence[str], None] = "9d1a2c3b4e55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "playbook_definitions",
        sa.Column("execution_order", sa.Integer(), nullable=False, server_default="1000"),
    )


def downgrade() -> None:
    op.drop_column("playbook_definitions", "execution_order")
