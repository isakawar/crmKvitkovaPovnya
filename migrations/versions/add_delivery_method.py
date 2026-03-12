"""Add delivery_method to delivery and order tables

Revision ID: add_delivery_method
Revises: add_delivery_routes
Create Date: 2026-03-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_delivery_method'
down_revision = 'add_delivery_routes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('delivery', sa.Column(
        'delivery_method',
        sa.String(32),
        nullable=False,
        server_default='courier'
    ))
    op.add_column('order', sa.Column(
        'delivery_method',
        sa.String(32),
        nullable=False,
        server_default='courier'
    ))


def downgrade():
    op.drop_column('delivery', 'delivery_method')
    op.drop_column('order', 'delivery_method')
