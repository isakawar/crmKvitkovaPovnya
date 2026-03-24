"""Add start_time to delivery_routes

Revision ID: add_route_start_time
Revises: add_recipient_phones_table
Create Date: 2026-03-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_route_start_time'
down_revision = 'add_recipient_phones_table'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('delivery_routes', sa.Column('start_time', sa.Time(), nullable=True))


def downgrade():
    op.drop_column('delivery_routes', 'start_time')
