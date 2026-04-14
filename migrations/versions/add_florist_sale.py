"""Add florist_sale table for offline sales tracking

Revision ID: add_florist_sale
Revises: add_taxi_courier
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_florist_sale'
down_revision = 'add_taxi_courier'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'florist_sale',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('florist_id', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('bonus_percent', sa.Numeric(5, 2), nullable=False, server_default=sa.text('5.0')),
        sa.Column('bonus_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['florist_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_florist_sale_florist_id', 'florist_sale', ['florist_id'])
    op.create_index('ix_florist_sale_created_at', 'florist_sale', ['created_at'])


def downgrade():
    op.drop_index('ix_florist_sale_created_at', table_name='florist_sale')
    op.drop_index('ix_florist_sale_florist_id', table_name='florist_sale')
    op.drop_table('florist_sale')
