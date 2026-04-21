"""Add transaction_type, expense_type, comment columns to transaction table

Revision ID: add_transaction_type_columns
Revises: add_transactions_table
Create Date: 2026-03-23 00:00:01.000000
"""
from alembic import op


revision = 'add_transaction_type_columns'
down_revision = 'add_transactions_table'
branch_labels = None
depends_on = None


def upgrade():
    # Columns transaction_type, expense_type, comment are already created in add_transactions_table.
    # Only ensure client_id is nullable to support debit transactions without a client.
    op.alter_column('transaction', 'client_id', nullable=True)


def downgrade():
    op.alter_column('transaction', 'client_id', nullable=False)
