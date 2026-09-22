"""Add reactions column to messaging_message

Telegram delivers reactions as a separate update carrying the whole current
set for a message, so the column holds that set as-is rather than one row per
reaction: [{"emoji": "\U0001f44d", "count": 1, "mine": true}].

Revision ID: add_message_reactions
Revises: add_messaging_message_indexes
Create Date: 2026-09-22 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op


revision = 'add_message_reactions'
down_revision = 'add_messaging_message_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('messaging_message', sa.Column('reactions', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('messaging_message', 'reactions')
