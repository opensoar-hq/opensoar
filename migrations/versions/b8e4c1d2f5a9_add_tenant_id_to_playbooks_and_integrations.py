"""add tenant_id to playbooks and integrations

Revision ID: b8e4c1d2f5a9
Revises: a7c9d2e1b4f6
Create Date: 2026-04-17

Adds a nullable tenant_id UUID column to playbook_definitions and
integration_instances so optional plugins can scope these resources to a
tenant.  A NULL value represents a globally visible resource shared across
tenants (for example, seeded built-ins).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b8e4c1d2f5a9"
down_revision: Union[str, Sequence[str], None] = "a7c9d2e1b4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "playbook_definitions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "integration_instances",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_playbook_definitions_tenant_id",
        "playbook_definitions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_integration_instances_tenant_id",
        "integration_instances",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_integration_instances_tenant_id", table_name="integration_instances")
    op.drop_index("ix_playbook_definitions_tenant_id", table_name="playbook_definitions")
    op.drop_column("integration_instances", "tenant_id")
    op.drop_column("playbook_definitions", "tenant_id")
