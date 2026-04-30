"""add created_by_id to transaction

Revision ID: add_transaction_created_by
Revises: add_subscription_snooze_fields, rename_followup_at
Create Date: 2026-04-30

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_transaction_created_by'
down_revision = ('add_subscription_snooze_fields', 'rename_followup_at')
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('transaction',
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True)
    )
    # backfill: link existing florist transactions via florist_sale
    op.execute("""
        UPDATE "transaction" t
        SET created_by_id = fs.florist_id
        FROM florist_sale fs
        WHERE fs.transaction_id = t.id
          AND t.created_by_id IS NULL
    """)


def downgrade():
    op.drop_column('transaction', 'created_by_id')
