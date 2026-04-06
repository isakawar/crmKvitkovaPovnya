"""Add contact_date column for draft subscriptions

Revision ID: add_subscription_draft
Revises: add_sub_renewal_reminder
Create Date: 2026-03-29

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_subscription_draft'
down_revision = 'add_sub_renewal_reminder'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('subscription', sa.Column('contact_date', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('subscription', 'contact_date')
