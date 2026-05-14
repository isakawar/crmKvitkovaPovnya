"""add before_data and after_data to activity_log

Revision ID: add_activity_log_before_after
Revises: transaction_amount_to_numeric
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_activity_log_before_after'
down_revision = 'add_florist_sale_account'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('activity_log', sa.Column('before_data', sa.JSON(), nullable=True))
    op.add_column('activity_log', sa.Column('after_data', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('activity_log', 'after_data')
    op.drop_column('activity_log', 'before_data')
