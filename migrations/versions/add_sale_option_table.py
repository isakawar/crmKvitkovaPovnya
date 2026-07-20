"""Add sale_option table for florist pricing calculator

Revision ID: add_sale_option_table
Revises: add_sub_parent_cl_disc
Create Date: 2026-07-19
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_sale_option_table'
down_revision = 'add_sub_parent_cl_disc'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'sale_option',
        sa.Column('id',         sa.Integer(),     nullable=False),
        sa.Column('name',       sa.String(100),   nullable=False),
        sa.Column('tiers_json', sa.Text(),         nullable=False),
        sa.Column('is_active',  sa.Boolean(),      nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(),      nullable=True),
        sa.Column('created_at', sa.DateTime(),     nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sale_option_is_active', 'sale_option', ['is_active'])


def downgrade():
    op.drop_index('ix_sale_option_is_active', table_name='sale_option')
    op.drop_table('sale_option')
