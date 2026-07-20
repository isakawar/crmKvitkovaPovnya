"""Add icon_filename to sale_option

Revision ID: add_sale_option_icon
Revises: add_sale_option_table
Create Date: 2026-07-20
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_sale_option_icon'
down_revision = 'add_sale_option_table'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sale_option', sa.Column('icon_filename', sa.String(255), nullable=True))


def downgrade():
    op.drop_column('sale_option', 'icon_filename')
