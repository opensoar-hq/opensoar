"""add analyst identities and nullable password hash

Revision ID: 6c2d5f4b8e91
Revises: c7d2e9f4a1b3
Create Date: 2026-04-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "6c2d5f4b8e91"
down_revision: str | None = "c7d2e9f4a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "analysts",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=True,
    )

    op.create_table(
        "analyst_identities",
        sa.Column("analyst_id", sa.Uuid(), nullable=False),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("issuer", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("claims_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["analyst_id"],
            ["analysts.id"],
            name=op.f("fk_analyst_identities_analyst_id_analysts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analyst_identities")),
        sa.UniqueConstraint(
            "provider_type",
            "issuer",
            "subject",
            name="uq_analyst_identities_provider_issuer_subject",
        ),
    )
    op.create_index(
        op.f("ix_analyst_identities_analyst_id"),
        "analyst_identities",
        ["analyst_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_analyst_identities_analyst_id"), table_name="analyst_identities")
    op.drop_table("analyst_identities")
    op.alter_column(
        "analysts",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=False,
    )
