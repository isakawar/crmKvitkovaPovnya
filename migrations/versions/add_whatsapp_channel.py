"""WhatsApp channel — WABA id + encrypted access token

Adds columns to `messaging_channel` for the WhatsApp adapter, connected via
Facebook Embedded Signup. See app/services/messaging/whatsapp.py.

Revision ID: add_whatsapp_channel
Revises: add_instagram_facebook_oauth
Create Date: 2026-09-15
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_whatsapp_channel'
down_revision = 'add_instagram_facebook_oauth'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('messaging_channel', sa.Column('wa_waba_id', sa.String(length=64), nullable=True))
    op.add_column('messaging_channel', sa.Column('wa_access_token_encrypted', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('messaging_channel', 'wa_access_token_encrypted')
    op.drop_column('messaging_channel', 'wa_waba_id')
