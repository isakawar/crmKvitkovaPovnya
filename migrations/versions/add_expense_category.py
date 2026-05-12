"""add expense_category table and FKs

Revision ID: add_expense_category
Revises: add_delivery_ind_resumed
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_expense_category'
down_revision = 'add_delivery_ind_resumed'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'expense_category',
        sa.Column('id',   sa.Integer, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(50),  nullable=False),
        sa.UniqueConstraint('name', name='uq_expense_category_name'),
        sa.UniqueConstraint('slug', name='uq_expense_category_slug'),
    )

    op.add_column('settings',
        sa.Column('category_id', sa.Integer, sa.ForeignKey('expense_category.id'), nullable=True)
    )

    op.add_column('transaction',
        sa.Column('expense_type_id', sa.Integer, sa.ForeignKey('settings.id'), nullable=True)
    )

    op.execute("""
        UPDATE "transaction" t
        SET expense_type_id = s.id
        FROM settings s
        WHERE s.type = 'expense_type' AND s.value = t.expense_type
    """)


def downgrade():
    op.drop_column('transaction', 'expense_type_id')
    op.drop_column('settings', 'category_id')
    op.drop_table('expense_category')
