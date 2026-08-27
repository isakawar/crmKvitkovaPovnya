"""Merge heads: wix integration + txn target account

Both add_wix_integration_tables and add_txn_target_account branch from
add_promo_codes. This empty merge migration unifies them into a single head
so `flask db upgrade` works on the integration/staging branch.

Revision ID: merge_wix_txn_target
Revises: add_txn_target_account, add_user_telegram_notifications
Create Date: 2026-08-27
"""
from alembic import op  # noqa: F401

revision = 'merge_wix_txn_target'
down_revision = ('add_txn_target_account', 'add_user_telegram_notifications')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
