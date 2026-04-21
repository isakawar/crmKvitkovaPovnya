"""Add Test delivery type to settings

Revision ID: add_test_delivery_type
Revises: add_delivery_method
Create Date: 2026-03-14 00:00:00.000000

"""
from alembic import op

revision = 'add_test_delivery_type'
down_revision = 'drop_delivery_rate'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "INSERT INTO settings (type, value) "
        "SELECT 'delivery_type', 'Test' "
        "WHERE NOT EXISTS (SELECT 1 FROM settings WHERE type='delivery_type' AND value='Test')"
    )


def downgrade():
    op.execute("DELETE FROM settings WHERE type='delivery_type' AND value='Test'")
