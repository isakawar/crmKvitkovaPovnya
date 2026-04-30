"""add snooze fields to subscription

Revision ID: add_subscription_snooze_fields
Revises: add_content_changed_at_to_route
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_subscription_snooze_fields'
down_revision = 'add_content_changed_at_to_route'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('subscription', sa.Column('snooze_until', sa.Date(), nullable=True))
    op.add_column('subscription', sa.Column('snooze_comment', sa.String(500), nullable=True))


def downgrade():
    op.drop_column('subscription', 'snooze_comment')
    op.drop_column('subscription', 'snooze_until')
