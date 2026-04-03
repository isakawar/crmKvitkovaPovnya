"""Add discount column to order and subscription tables

Revision ID: add_discount_to_order_subscription
Revises: add_subscription_draft_fields
Create Date: 2026-03-31

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_order_discount'
down_revision = 'add_subscription_draft_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order', sa.Column('discount', sa.Integer(), nullable=True))
    op.add_column('subscription', sa.Column('discount', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('order', 'discount')
    op.drop_column('subscription', 'discount')
