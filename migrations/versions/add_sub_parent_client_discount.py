"""Add parent_subscription_id to subscription and discount to client

Revision ID: add_sub_parent_cl_disc
Revises: add_order_sub_to_txn
Create Date: 2026-07-08

"""
import sqlalchemy as sa
from alembic import op

revision = 'add_sub_parent_cl_disc'
down_revision = 'add_order_sub_to_txn'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('subscription', sa.Column('parent_subscription_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_sub_parent_id', 'subscription', 'subscription',
        ['parent_subscription_id'], ['id'], ondelete='SET NULL'
    )
    op.add_column('client', sa.Column('discount', sa.Integer(), nullable=True))


def downgrade():
    op.drop_constraint('fk_sub_parent_id', 'subscription', type_='foreignkey')
    op.drop_column('subscription', 'parent_subscription_id')
    op.drop_column('client', 'discount')
