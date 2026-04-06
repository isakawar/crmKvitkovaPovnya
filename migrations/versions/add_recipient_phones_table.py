"""Add recipient_phone table for multiple phones per order

Revision ID: add_recipient_phones_table
Revises: add_transactions_table
Create Date: 2026-03-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_recipient_phones_table'
down_revision = 'add_transaction_type_columns'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'recipient_phone',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('position', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['order.id'], name='fk_recipient_phone_order_id'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('recipient_phone')
