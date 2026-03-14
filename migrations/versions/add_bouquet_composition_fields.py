"""Add bouquet_type and composition_type to order and delivery tables

Revision ID: add_bouquet_composition_fields
Revises: add_address_comment
Create Date: 2026-03-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_bouquet_composition_fields'
down_revision = 'add_address_comment'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order', sa.Column('bouquet_type', sa.String(64), nullable=True))
    op.add_column('order', sa.Column('composition_type', sa.String(64), nullable=True))
    op.add_column('delivery', sa.Column('bouquet_type', sa.String(64), nullable=True))
    op.add_column('delivery', sa.Column('composition_type', sa.String(64), nullable=True))


def downgrade():
    op.drop_column('order', 'bouquet_type')
    op.drop_column('order', 'composition_type')
    op.drop_column('delivery', 'bouquet_type')
    op.drop_column('delivery', 'composition_type')
