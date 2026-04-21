"""Add is_wedding column to subscription table

Revision ID: add_subscription_is_wedding
Revises: add_performance_indexes
Create Date: 2026-03-24 00:00:00.000000

"""
revision = 'add_subscription_is_wedding'
down_revision = 'add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    # is_wedding already created in refactor_subscription_order migration
    pass


def downgrade():
    pass
