"""add embedding to articles

Revision ID: 7f3c2a1d9e8b
Revises: 3096aefcac34
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '7f3c2a1d9e8b'
down_revision: Union[str, Sequence[str], None] = '3096aefcac34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column('articles', sa.Column('embedding', Vector(384), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('articles', 'embedding')
    op.execute("DROP EXTENSION IF EXISTS vector")
