"""Add display_name column to user table

Revision ID: add_display_name_to_user
Revises: add_transaction_type_columns
Create Date: 2026-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_display_name_to_user'
down_revision = 'add_florist_sale'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('display_name', sa.String(120), nullable=True))


def downgrade():
    op.drop_column('user', 'display_name')
