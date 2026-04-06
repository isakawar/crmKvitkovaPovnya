"""Add cached_result_json and cached_at to delivery_routes

Revision ID: add_route_cache
Revises: add_florist_status_to_delivery
Create Date: 2026-03-20 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_route_cache'
down_revision = 'add_florist_status_to_delivery'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('delivery_routes', sa.Column('cached_result_json', sa.Text(), nullable=True))
    op.add_column('delivery_routes', sa.Column('cached_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('delivery_routes', 'cached_at')
    op.drop_column('delivery_routes', 'cached_result_json')
