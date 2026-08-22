"""Add target_payment_account_id to transaction for card-to-card transfers

Revision ID: add_transaction_target_payment_account
Revises: add_promo_codes
Create Date: 2026-08-22
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_transaction_target_payment_account'
down_revision = 'add_promo_codes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('transaction', sa.Column('target_payment_account_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_transaction_target_payment_account_id',
        'transaction', 'settings',
        ['target_payment_account_id'], ['id'],
    )


def downgrade():
    op.drop_constraint('fk_transaction_target_payment_account_id', 'transaction', type_='foreignkey')
    op.drop_column('transaction', 'target_payment_account_id')
