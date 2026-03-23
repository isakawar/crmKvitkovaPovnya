"""Add transaction_type, expense_type, comment columns to transaction table

Revision ID: add_transaction_type_columns
Revises: add_transactions_table
Create Date: 2026-03-23 00:00:01.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_transaction_type_columns'
down_revision = 'add_transactions_table'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('transaction', sa.Column('transaction_type', sa.String(length=16), nullable=False, server_default='credit'))
    op.add_column('transaction', sa.Column('expense_type', sa.String(length=64), nullable=True))
    op.add_column('transaction', sa.Column('comment', sa.Text(), nullable=True))

    # Make client_id nullable to support debit transactions without a client
    op.alter_column('transaction', 'client_id', nullable=True)


def downgrade():
    op.alter_column('transaction', 'client_id', nullable=False)
    op.drop_column('transaction', 'comment')
    op.drop_column('transaction', 'expense_type')
    op.drop_column('transaction', 'transaction_type')
