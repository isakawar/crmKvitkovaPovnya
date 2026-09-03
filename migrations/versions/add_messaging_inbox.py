"""Omnichannel inbox — messaging channels, conversations, messages

Adds the tables for the in-CRM chat/inbox: `messaging_channel` (a configured
corporate account), `messaging_channel_access` (which managers see it),
`messaging_conversation` (one dialog with a contact) and `messaging_message`
(a single inbound/outbound message). Channel-agnostic; Telegram is the first
adapter.

Revision ID: add_messaging_inbox
Revises: add_address_coordinates
Create Date: 2026-09-03
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_messaging_inbox'
down_revision = 'add_address_coordinates'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'messaging_channel',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('channel_type', sa.String(length=20), nullable=False, server_default='telegram'),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('external_id', sa.String(length=128), nullable=True),
        sa.Column('webhook_secret', sa.String(length=64), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'messaging_channel_access',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('channel_id', sa.Integer(),
                  sa.ForeignKey('messaging_channel.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('channel_id', 'user_id', name='uq_messaging_channel_access'),
    )
    op.create_index('ix_messaging_channel_access_channel_id', 'messaging_channel_access', ['channel_id'])
    op.create_index('ix_messaging_channel_access_user_id', 'messaging_channel_access', ['user_id'])

    op.create_table(
        'messaging_conversation',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('channel_id', sa.Integer(),
                  sa.ForeignKey('messaging_channel.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_chat_id', sa.String(length=64), nullable=False),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('contact_username', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=32), nullable=True),
        sa.Column('client_id', sa.Integer(),
                  sa.ForeignKey('client.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_user_id', sa.Integer(),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='open'),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('last_message_preview', sa.String(length=200), nullable=True),
        sa.Column('last_message_direction', sa.String(length=4), nullable=True),
        sa.Column('unread_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('channel_id', 'external_chat_id', name='uq_conversation_channel_chat'),
    )
    op.create_index('ix_messaging_conversation_channel_id', 'messaging_conversation', ['channel_id'])
    op.create_index('ix_messaging_conversation_last_message_at', 'messaging_conversation', ['last_message_at'])

    op.create_table(
        'messaging_message',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('conversation_id', sa.Integer(),
                  sa.ForeignKey('messaging_conversation.id', ondelete='CASCADE'), nullable=False),
        sa.Column('direction', sa.String(length=4), nullable=False),
        sa.Column('external_message_id', sa.String(length=64), nullable=True),
        sa.Column('sender_user_id', sa.Integer(),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('media', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='received'),
        sa.Column('error', sa.String(length=500), nullable=True),
        sa.Column('tg_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_messaging_message_conversation_id', 'messaging_message', ['conversation_id'])
    op.create_index('ix_messaging_message_created_at', 'messaging_message', ['created_at'])


def downgrade():
    op.drop_table('messaging_message')
    op.drop_table('messaging_conversation')
    op.drop_table('messaging_channel_access')
    op.drop_table('messaging_channel')
