"""Add reply_to_message_id to messaging_message

Only used for outbound Telegram (business + personal) replies — other
channels' send APIs don't support quoting an arbitrary message.

Revision ID: add_message_reply_to
Revises: add_message_reactions
Create Date: 2026-09-22 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op


revision = 'add_message_reply_to'
down_revision = 'add_message_reactions'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('messaging_message',
                  sa.Column('reply_to_message_id', sa.Integer(),
                           sa.ForeignKey('messaging_message.id', ondelete='SET NULL'),
                           nullable=True))


def downgrade():
    op.drop_column('messaging_message', 'reply_to_message_id')
