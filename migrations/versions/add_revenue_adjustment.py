"""add revenue_adjustment table

Revision ID: add_revenue_adjustment
Revises: add_txn_payment_account
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_revenue_adjustment'
down_revision = 'add_txn_payment_account'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'revenue_adjustment',
        sa.Column('id',              sa.Integer(),  nullable=False),
        sa.Column('client_id',       sa.Integer(),  nullable=False),
        sa.Column('subscription_id', sa.Integer(),  nullable=True),
        sa.Column('month',           sa.Date(),     nullable=False),
        sa.Column('adj_charged',     sa.Integer(),  nullable=False, server_default='0'),
        sa.Column('adj_paid',        sa.Integer(),  nullable=False, server_default='0'),
        sa.Column('created_at',      sa.DateTime(), nullable=True),
        sa.Column('updated_at',      sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'],       ['client.id']),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscription.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_revenue_adj_client_month', 'revenue_adjustment', ['client_id', 'month'])


def downgrade():
    op.drop_index('ix_revenue_adj_client_month', table_name='revenue_adjustment')
    op.drop_table('revenue_adjustment')
