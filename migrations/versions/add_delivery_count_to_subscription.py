"""Add delivery_count column to subscription table

Revision ID: add_delivery_count_to_subscription
Revises: add_order_discount
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_sub_delivery_count'
down_revision = 'add_email_to_client'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('subscription', sa.Column('delivery_count', sa.Integer(), nullable=False, server_default='4'))


def downgrade():
    op.drop_column('subscription', 'delivery_count')
