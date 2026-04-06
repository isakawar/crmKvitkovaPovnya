"""Add is_renewal_reminder column to subscription table

Revision ID: add_subscription_renewal_reminder
Revises: add_subscription_is_wedding
Create Date: 2026-03-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_sub_renewal_reminder'
down_revision = 'add_subscription_is_wedding'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('subscription', sa.Column(
        'is_renewal_reminder', sa.Boolean(), nullable=False, server_default=sa.text('false')
    ))


def downgrade():
    op.drop_column('subscription', 'is_renewal_reminder')
