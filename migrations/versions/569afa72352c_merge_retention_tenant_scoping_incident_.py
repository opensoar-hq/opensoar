"""merge retention + tenant scoping + incident templates heads

Revision ID: 569afa72352c
Revises: b8d4e6f12a77, b8e4c1d2f5a9, b8f3d2c1a9e7
Create Date: 2026-04-17 14:15:42.676802

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '569afa72352c'
down_revision: Union[str, Sequence[str], None] = ('b8d4e6f12a77', 'b8e4c1d2f5a9', 'b8f3d2c1a9e7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
