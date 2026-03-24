"""Add is_wedding column to subscription table

Revision ID: add_subscription_is_wedding
Revises: add_performance_indexes
Create Date: 2026-03-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_subscription_is_wedding'
down_revision = 'add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('subscription', sa.Column('is_wedding', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    op.drop_column('subscription', 'is_wedding')
