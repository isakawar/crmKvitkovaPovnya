"""Add transactions table

Revision ID: add_transactions_table
Revises: add_certificates_table
Create Date: 2026-03-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_transactions_table'
down_revision = 'add_certificates_table'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(length=16), nullable=False, server_default='credit'),
        sa.Column('client_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('payment_type', sa.String(length=32), nullable=True),
        sa.Column('expense_type', sa.String(length=64), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['client.id'], name='fk_transaction_client_id'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('transaction')
