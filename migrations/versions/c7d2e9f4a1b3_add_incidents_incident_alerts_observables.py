"""add incidents, incident_alerts, observables tables

Revision ID: c7d2e9f4a1b3
Revises: b5e1a3c8d2f7
Create Date: 2026-04-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "c7d2e9f4a1b3"
down_revision: str | None = "b5e1a3c8d2f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("assigned_to", sa.Uuid(), nullable=True),
        sa.Column("assigned_username", sa.String(100), nullable=True),
        sa.Column("tags", ARRAY(sa.String()), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_to"], ["analysts.id"], name="fk_incidents_assigned_to_analysts", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_incidents"),
    )

    op.create_table(
        "incident_alerts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], name="fk_incident_alerts_incident_id_incidents", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], name="fk_incident_alerts_alert_id_alerts", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_incident_alerts"),
    )
    op.create_index("ix_incident_alerts_incident_id", "incident_alerts", ["incident_id"])
    op.create_index("ix_incident_alerts_alert_id", "incident_alerts", ["alert_id"])

    op.create_table(
        "observables",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("value", sa.String(1000), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("enrichment_status", sa.String(20), nullable=False),
        sa.Column("enrichments", JSONB(), nullable=True),
        sa.Column("tags", ARRAY(sa.String()), nullable=True),
        sa.Column("alert_id", sa.Uuid(), nullable=True),
        sa.Column("incident_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], name="fk_observables_alert_id_alerts", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], name="fk_observables_incident_id_incidents", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_observables"),
    )


def downgrade() -> None:
    op.drop_table("observables")
    op.drop_index("ix_incident_alerts_alert_id", table_name="incident_alerts")
    op.drop_index("ix_incident_alerts_incident_id", table_name="incident_alerts")
    op.drop_table("incident_alerts")
    op.drop_table("incidents")
