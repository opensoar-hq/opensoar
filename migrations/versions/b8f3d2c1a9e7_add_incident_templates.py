"""add incident_templates table

Revision ID: b8f3d2c1a9e7
Revises: a7c9d2e1b4f6
Create Date: 2026-04-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b8f3d2c1a9e7"
down_revision: Union[str, Sequence[str], None] = "a7c9d2e1b4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incident_templates",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "default_severity",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'medium'"),
        ),
        sa.Column(
            "default_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "playbook_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "observable_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_incident_templates"),
    )
    op.create_index(
        "ix_incident_templates_tenant_id",
        "incident_templates",
        ["tenant_id"],
    )

    # Seed the built-in templates so fresh installs have starter coverage
    # for the three most common incident classes.
    op.execute(
        """
        INSERT INTO incident_templates
            (name, description, default_severity, default_tags,
             playbook_ids, observable_types, tenant_id)
        VALUES
            (
                'Phishing',
                'Email-based credential harvest or malware delivery.',
                'high',
                '["phishing", "email"]'::jsonb,
                '[]'::jsonb,
                '["email", "url", "domain", "hash"]'::jsonb,
                NULL
            ),
            (
                'Ransomware',
                'Encryption-based destructive attack on endpoints or file shares.',
                'critical',
                '["ransomware", "malware", "destructive"]'::jsonb,
                '[]'::jsonb,
                '["hash", "ip", "domain", "hostname"]'::jsonb,
                NULL
            ),
            (
                'Data Exfiltration',
                'Unauthorized outbound transfer of sensitive data.',
                'high',
                '["data-exfil", "insider-threat", "dlp"]'::jsonb,
                '[]'::jsonb,
                '["ip", "domain", "url", "hostname"]'::jsonb,
                NULL
            )
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_incident_templates_tenant_id",
        table_name="incident_templates",
    )
    op.drop_table("incident_templates")
