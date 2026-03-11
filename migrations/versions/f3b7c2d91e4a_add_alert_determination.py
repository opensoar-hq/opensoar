"""add alert determination

Revision ID: f3b7c2d91e4a
Revises: e4ae68da1d53
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f3b7c2d91e4a"
down_revision: str | None = "a09471a0a2d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("determination", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("alerts", "determination")
