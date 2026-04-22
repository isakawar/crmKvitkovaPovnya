"""add activity_log table

Revision ID: add_activity_log
Revises: add_last_seen_to_user
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_activity_log'
down_revision = 'add_last_seen_to_user'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'activity_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_label', sa.String(100), nullable=True),
        sa.Column('action', sa.String(20), nullable=True),
        sa.Column('entity_type', sa.String(30), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_activity_log_created_at', 'activity_log', ['created_at'])


def downgrade():
    op.drop_index('ix_activity_log_created_at', table_name='activity_log')
    op.drop_table('activity_log')
