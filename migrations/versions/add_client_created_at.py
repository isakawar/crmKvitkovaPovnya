"""Add created_at to client table

Revision ID: add_client_created_at
Revises: add_route_start_time
Create Date: 2026-03-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_client_created_at'
down_revision = 'add_route_start_time'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('client', sa.Column('created_at', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('client', 'created_at')
