"""Add composite index on messaging_message(conversation_id, external_message_id)

Revision ID: add_messaging_message_indexes
Revises: add_whatsapp_channel
Create Date: 2026-09-21 00:00:00.000000

"""
from alembic import op


revision = 'add_messaging_message_indexes'
down_revision = 'add_whatsapp_channel'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'ix_messaging_message_conv_extmsg', 'messaging_message',
        ['conversation_id', 'external_message_id'],
    )


def downgrade():
    op.drop_index('ix_messaging_message_conv_extmsg', 'messaging_message')
