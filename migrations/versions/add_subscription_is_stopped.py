"""add is_stopped to subscription

Revision ID: add_subscription_is_stopped
Revises: add_transaction_created_by
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_subscription_is_stopped'
down_revision = 'add_transaction_created_by'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'subscription',
        sa.Column('is_stopped', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )


def downgrade():
    op.drop_column('subscription', 'is_stopped')
