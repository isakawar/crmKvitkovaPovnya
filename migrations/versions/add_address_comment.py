"""Add address_comment to order and delivery tables

Revision ID: add_address_comment
Revises: add_test_delivery_type
Create Date: 2026-03-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_address_comment'
down_revision = 'add_test_delivery_type'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order', sa.Column('address_comment', sa.Text(), nullable=True))
    op.add_column('delivery', sa.Column('address_comment', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('order', 'address_comment')
    op.drop_column('delivery', 'address_comment')
