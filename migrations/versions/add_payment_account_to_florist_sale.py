"""add payment_account_id to florist_sale

Revision ID: add_payment_account_to_florist_sale
Revises: transaction_amount_to_numeric
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_florist_sale_account'
down_revision = 'transaction_amount_to_numeric'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('florist_sale',
        sa.Column('payment_account_id', sa.Integer(), sa.ForeignKey('settings.id'), nullable=True)
    )


def downgrade():
    op.drop_column('florist_sale', 'payment_account_id')
