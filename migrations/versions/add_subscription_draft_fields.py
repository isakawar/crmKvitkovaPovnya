"""Add draft_comment, draft_bank_link, draft_wedding_date to subscription

Revision ID: add_subscription_draft_fields
Revises: add_subscription_draft
Create Date: 2026-03-29

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_subscription_draft_fields'
down_revision = 'add_subscription_draft'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('subscription', sa.Column('draft_comment', sa.Text(), nullable=True))
    op.add_column('subscription', sa.Column('draft_bank_link', sa.String(512), nullable=True))
    op.add_column('subscription', sa.Column('draft_wedding_date', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('subscription', 'draft_wedding_date')
    op.drop_column('subscription', 'draft_bank_link')
    op.drop_column('subscription', 'draft_comment')
