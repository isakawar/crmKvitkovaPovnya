"""add payment_type and transaction_id to florist_sale

Revision ID: add_florist_sale_payment_type
Revises: add_order_photos_table
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_florist_sale_payment_type'
down_revision = 'add_order_photos_table'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('florist_sale', sa.Column('payment_type', sa.String(32), nullable=True))
    op.add_column('florist_sale', sa.Column('transaction_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_florist_sale_transaction_id',
        'florist_sale', 'transaction',
        ['transaction_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade():
    op.drop_constraint('fk_florist_sale_transaction_id', 'florist_sale', type_='foreignkey')
    op.drop_column('florist_sale', 'transaction_id')
    op.drop_column('florist_sale', 'payment_type')
