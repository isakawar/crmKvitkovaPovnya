"""add last_seen to user

Revision ID: add_last_seen_to_user
Revises: add_courier_profile_fields
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_last_seen_to_user'
down_revision = 'add_courier_profile_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('last_seen', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('user', 'last_seen')
