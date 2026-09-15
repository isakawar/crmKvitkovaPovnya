"""Instagram via Facebook Login OAuth — Page id + encrypted Page access token

Adds columns to `messaging_channel` for the OAuth-connected Instagram adapter
(replaces the manual App Secret/Access Token setup). See
app/services/messaging/facebook_oauth.py and instagram_dm.py.

Revision ID: add_instagram_facebook_oauth
Revises: add_telegram_personal_channel
Create Date: 2026-09-15
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_instagram_facebook_oauth'
down_revision = 'add_telegram_personal_channel'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('messaging_channel', sa.Column('fb_page_id', sa.String(length=64), nullable=True))
    op.add_column('messaging_channel', sa.Column('fb_page_access_token_encrypted', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('messaging_channel', 'fb_page_access_token_encrypted')
    op.drop_column('messaging_channel', 'fb_page_id')
