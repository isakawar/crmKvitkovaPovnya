"""Add content_changed_at to delivery_routes

Revision ID: add_content_changed_at_to_route
Revises: add_route_dispatch_log
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_content_changed_at_to_route'
down_revision = 'add_route_dispatch_log'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('delivery_routes', sa.Column('content_changed_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('delivery_routes', 'content_changed_at')
