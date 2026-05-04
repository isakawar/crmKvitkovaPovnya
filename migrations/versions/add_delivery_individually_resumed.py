"""add individually_resumed to delivery

Revision ID: add_delivery_ind_resumed
Revises: seed_expense_types
Create Date: 2026-05-04

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_delivery_ind_resumed'
down_revision = 'seed_expense_types'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('delivery', sa.Column(
        'individually_resumed', sa.Boolean(), nullable=False, server_default=sa.false()
    ))


def downgrade():
    op.drop_column('delivery', 'individually_resumed')
