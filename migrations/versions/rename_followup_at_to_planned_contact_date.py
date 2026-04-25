"""rename followup_at to planned_contact_date

Revision ID: rename_followup_at
Revises: add_activity_log
Create Date: 2026-04-24

"""
from alembic import op

revision = 'rename_followup_at'
down_revision = 'add_activity_log'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE subscription RENAME COLUMN followup_at TO planned_contact_date')


def downgrade():
    op.execute('ALTER TABLE subscription RENAME COLUMN planned_contact_date TO followup_at')
