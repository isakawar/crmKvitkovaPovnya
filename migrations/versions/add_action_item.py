"""add action_item and action_item_recipient tables

Revision ID: add_action_item
Revises: add_activity_log_before_after
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_action_item'
down_revision = 'add_activity_log_before_after'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'action_item',
        sa.Column('id',              sa.Integer(),    nullable=False),
        sa.Column('title',           sa.String(200),  nullable=False),
        sa.Column('description',     sa.Text(),       nullable=True),
        sa.Column('due_at',          sa.DateTime(),   nullable=True),
        sa.Column('completion_mode', sa.String(20),   nullable=False, server_default='all'),
        sa.Column('created_at',      sa.DateTime(),   nullable=False),
        sa.Column('created_by',      sa.Integer(),    nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'action_item_recipient',
        sa.Column('id',             sa.Integer(),  nullable=False),
        sa.Column('action_item_id', sa.Integer(),  nullable=False),
        sa.Column('user_id',        sa.Integer(),  nullable=False),
        sa.Column('status',         sa.String(20), nullable=False, server_default='pending'),
        sa.Column('completed_at',   sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['action_item_id'], ['action_item.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'],        ['user.id'],        ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_action_item_recipient_action_item_id', 'action_item_recipient', ['action_item_id'])
    op.create_index('ix_action_item_recipient_user_id',        'action_item_recipient', ['user_id'])
    op.create_index('ix_action_item_recipient_status',         'action_item_recipient', ['status'])


def downgrade():
    op.drop_index('ix_action_item_recipient_status',         table_name='action_item_recipient')
    op.drop_index('ix_action_item_recipient_user_id',        table_name='action_item_recipient')
    op.drop_index('ix_action_item_recipient_action_item_id', table_name='action_item_recipient')
    op.drop_table('action_item_recipient')
    op.drop_table('action_item')
