"""transaction amount and client credits to Numeric(10,2)

Revision ID: transaction_amount_to_numeric
Revises: add_revenue_adjustment
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa

revision = 'transaction_amount_to_numeric'
down_revision = 'add_revenue_adjustment'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'transaction', 'amount',
        existing_type=sa.Integer(),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
        postgresql_using='amount::numeric(10,2)',
    )
    op.alter_column(
        'client', 'credits',
        existing_type=sa.Integer(),
        type_=sa.Numeric(10, 2),
        existing_nullable=True,
        postgresql_using='credits::numeric(10,2)',
    )


def downgrade():
    op.alter_column(
        'client', 'credits',
        existing_type=sa.Numeric(10, 2),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using='credits::integer',
    )
    op.alter_column(
        'transaction', 'amount',
        existing_type=sa.Numeric(10, 2),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using='amount::integer',
    )
