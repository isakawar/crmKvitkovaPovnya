"""merge heads before expense types

Revision ID: merge_heads_before_expense_types
Revises: add_florist_sale_payment_type, add_subscription_is_stopped, add_subscription_snooze_fields
Create Date: 2026-05-02

"""
from alembic import op
import sqlalchemy as sa

revision = 'merge_heads_before_expense_types'
down_revision = ('add_florist_sale_payment_type', 'add_subscription_is_stopped', 'add_subscription_snooze_fields')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
