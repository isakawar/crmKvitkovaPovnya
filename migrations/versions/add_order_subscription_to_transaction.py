"""add order_id and subscription_id to transaction

Revision ID: add_order_subscription_to_transaction
Revises: add_action_item
Create Date: 2026-07-08

"""
import sqlalchemy as sa
from alembic import op

revision = 'add_order_sub_to_txn'
down_revision = 'add_action_item'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('transaction', sa.Column('order_id', sa.Integer(), nullable=True))
    op.add_column('transaction', sa.Column('subscription_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_transaction_order_id', 'transaction', 'order', ['order_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_transaction_subscription_id', 'transaction', 'subscription', ['subscription_id'], ['id'], ondelete='SET NULL'
    )


def downgrade():
    op.drop_constraint('fk_transaction_subscription_id', 'transaction', type_='foreignkey')
    op.drop_constraint('fk_transaction_order_id', 'transaction', type_='foreignkey')
    op.drop_column('transaction', 'subscription_id')
    op.drop_column('transaction', 'order_id')
