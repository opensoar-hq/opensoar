"""add partner to integrations and playbooks

Revision ID: 9d1a2c3b4e55
Revises: 6c2d5f4b8e91
Create Date: 2026-04-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d1a2c3b4e55"
down_revision: Union[str, Sequence[str], None] = "6c2d5f4b8e91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("integration_instances", sa.Column("partner", sa.String(length=100), nullable=True))
    op.add_column("playbook_definitions", sa.Column("partner", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("playbook_definitions", "partner")
    op.drop_column("integration_instances", "partner")
