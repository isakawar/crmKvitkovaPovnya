"""Add subscription followup fields to order

Revision ID: add_subscription_followup_status
Revises: add_delivery_method
Create Date: 2026-03-17 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_subscription_followup_status'
down_revision = 'add_prices_table'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order', sa.Column('subscription_followup_status', sa.String(length=32), nullable=True))
    op.add_column('order', sa.Column('subscription_followup_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('order', 'subscription_followup_at')
    op.drop_column('order', 'subscription_followup_status')
