"""Add prices table

Revision ID: add_prices_table
Revises: add_test_delivery_type
Create Date: 2026-03-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_prices_table'
down_revision = 'add_bouquet_composition_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subscription_type_id', sa.Integer(), nullable=False),
        sa.Column('size_id', sa.Integer(), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['subscription_type_id'], ['settings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['size_id'], ['settings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subscription_type_id', 'size_id', name='uq_price_sub_size'),
    )


def downgrade():
    op.drop_table('prices')
