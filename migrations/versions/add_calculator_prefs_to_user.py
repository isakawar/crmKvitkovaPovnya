"""Add calculator_prefs to user

Revision ID: add_calculator_prefs_to_user
Revises: add_sale_option_icon
Create Date: 2026-07-20
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_calculator_prefs_to_user'
down_revision = 'add_sale_option_icon'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('calculator_prefs', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('user', 'calculator_prefs')
