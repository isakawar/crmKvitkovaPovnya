"""Add Telegram fields to User and wix_lead_notification table

Revision ID: add_user_telegram_and_lead_notifications
Revises: add_wix_integration_tables
Create Date: 2026-08-24
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_user_telegram_and_lead_notifications'
down_revision = 'add_wix_integration_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('phone', sa.String(length=32), nullable=True))
    op.add_column('user', sa.Column('telegram_chat_id', sa.BigInteger(), nullable=True))
    op.add_column('user', sa.Column('telegram_username', sa.String(length=64), nullable=True))
    op.add_column('user', sa.Column('telegram_registered', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('user', sa.Column('telegram_notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('user', sa.Column('last_telegram_activity', sa.DateTime(), nullable=True))
    op.create_unique_constraint('uq_user_phone', 'user', ['phone'])
    op.create_unique_constraint('uq_user_telegram_chat_id', 'user', ['telegram_chat_id'])

    op.create_table(
        'wix_lead_notification',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('wix_lead_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('telegram_chat_id', sa.BigInteger(), nullable=False),
        sa.Column('telegram_message_id', sa.Integer(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['wix_lead_id'], ['wix_lead.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_wix_lead_notification_wix_lead_id', 'wix_lead_notification', ['wix_lead_id'])


def downgrade():
    op.drop_index('ix_wix_lead_notification_wix_lead_id', table_name='wix_lead_notification')
    op.drop_table('wix_lead_notification')
    op.drop_constraint('uq_user_telegram_chat_id', 'user', type_='unique')
    op.drop_constraint('uq_user_phone', 'user', type_='unique')
    op.drop_column('user', 'last_telegram_activity')
    op.drop_column('user', 'telegram_notifications_enabled')
    op.drop_column('user', 'telegram_registered')
    op.drop_column('user', 'telegram_username')
    op.drop_column('user', 'telegram_chat_id')
    op.drop_column('user', 'phone')
