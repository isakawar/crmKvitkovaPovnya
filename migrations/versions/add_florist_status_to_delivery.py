"""Add florist_status to delivery

Revision ID: add_florist_status_to_delivery
Revises: add_subscription_followup_status
Create Date: 2026-03-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_florist_status_to_delivery'
down_revision = 'add_subscription_followup_status'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('delivery', sa.Column('florist_status', sa.String(length=32), nullable=True))


def downgrade():
    op.drop_column('delivery', 'florist_status')

