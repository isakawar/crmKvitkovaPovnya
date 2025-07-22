"""make street nullable for pickup orders

Revision ID: c97ef87e9bd5
Revises: 42e5784b0e64
Create Date: 2025-07-07 02:53:59.521302

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c97ef87e9bd5'
down_revision: Union[str, Sequence[str], None] = '42e5784b0e64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite doesn't support ALTER COLUMN to change nullability
    # We need to recreate the table
    with op.batch_alter_table('order') as batch_op:
        batch_op.alter_column('street', nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('order') as batch_op:
        batch_op.alter_column('street', nullable=False) 