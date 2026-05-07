"""add sort_order to settings for size ordering

Revision ID: add_size_sort_order
Revises: add_billing_fields
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_size_sort_order'
down_revision = 'add_billing_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('settings', sa.Column('sort_order', sa.Integer(), nullable=True))
    op.execute("""
        UPDATE settings SET sort_order = CASE value
            WHEN 'S'       THEN 1
            WHEN 'M'       THEN 2
            WHEN 'L'       THEN 3
            WHEN 'XL'      THEN 4
            WHEN 'XXL'     THEN 5
            WHEN 'Власний' THEN 6
            ELSE 99
        END
        WHERE type = 'size'
    """)


def downgrade():
    op.drop_column('settings', 'sort_order')
