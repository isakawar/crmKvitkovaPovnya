"""Add billing fields: Price.subscription_type_id nullable, Order.charged_amount, Transaction.delivery_id

Revision ID: add_billing_fields
Revises: add_cycle_number_to_order
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_billing_fields'
down_revision = 'add_cycle_number_to_order'
branch_labels = None
depends_on = None


def upgrade():
    # Price.subscription_type_id → nullable (NULL = one-time order price)
    op.alter_column('prices', 'subscription_type_id',
                    existing_type=sa.Integer(),
                    nullable=True)

    # Order.charged_amount — price snapshot at creation time (after discount)
    op.add_column('order', sa.Column('charged_amount', sa.Integer(), nullable=True))

    # Transaction.delivery_id — links delivery_charge transaction to a specific delivery
    op.add_column('transaction', sa.Column('delivery_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_transaction_delivery_id',
        'transaction', 'delivery',
        ['delivery_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade():
    op.drop_constraint('fk_transaction_delivery_id', 'transaction', type_='foreignkey')
    op.drop_column('transaction', 'delivery_id')
    op.drop_column('order', 'charged_amount')
    op.alter_column('prices', 'subscription_type_id',
                    existing_type=sa.Integer(),
                    nullable=False)
