"""Add payment_account_id to transaction

Revision ID: add_payment_account_to_transaction
Revises: add_price_presets
Create Date: 2026-05-07

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_txn_payment_account'
down_revision = 'add_price_presets'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('transaction', sa.Column(
        'payment_account_id', sa.Integer(),
        sa.ForeignKey('settings.id'), nullable=True
    ))


def downgrade():
    op.drop_column('transaction', 'payment_account_id')
