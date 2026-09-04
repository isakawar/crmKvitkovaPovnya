"""Telegram "personal number" channel — MTProto login fields

Adds columns to `messaging_channel` for the telegram_personal adapter
(phone number + encrypted session strings for the login handshake and the
final authorized session). See app/services/messaging/telegram_personal*.py.

Revision ID: add_telegram_personal_channel
Revises: add_messaging_inbox
Create Date: 2026-09-04
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_telegram_personal_channel'
down_revision = 'add_messaging_inbox'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('messaging_channel', sa.Column('phone_number', sa.String(length=32), nullable=True))
    op.add_column('messaging_channel', sa.Column('session_encrypted', sa.Text(), nullable=True))
    op.add_column('messaging_channel', sa.Column('pending_session_encrypted', sa.Text(), nullable=True))
    op.add_column('messaging_channel', sa.Column('pending_phone_code_hash', sa.String(length=128), nullable=True))


def downgrade():
    op.drop_column('messaging_channel', 'pending_phone_code_hash')
    op.drop_column('messaging_channel', 'pending_session_encrypted')
    op.drop_column('messaging_channel', 'session_encrypted')
    op.drop_column('messaging_channel', 'phone_number')
