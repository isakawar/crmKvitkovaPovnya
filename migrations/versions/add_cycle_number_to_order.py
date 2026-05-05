"""Add cycle_number to order

Revision ID: add_cycle_number_to_order
Revises: seed_required_expense_categories
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_cycle_number_to_order'
down_revision = 'seed_required_expense_categories'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order', sa.Column('cycle_number', sa.Integer(), nullable=True))

    op.execute("""
        UPDATE "order"
        SET cycle_number = FLOOR((sequence_number - 1) / 4) + 1
        WHERE subscription_id IS NOT NULL
          AND sequence_number IS NOT NULL
    """)


def downgrade():
    op.drop_column('order', 'cycle_number')
