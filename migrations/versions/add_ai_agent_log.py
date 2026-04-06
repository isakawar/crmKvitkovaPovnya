"""Add ai_agent_log table

Revision ID: add_ai_agent_log
Revises: add_transaction_type_columns
Create Date: 2026-04-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_ai_agent_log'
down_revision = 'add_order_discount'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ai_agent_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('before_data', sa.JSON(), nullable=True),
        sa.Column('after_data', sa.JSON(), nullable=True),
        sa.Column('ai_message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_ai_agent_log_user_id'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('ai_agent_log')
