"""Extend order text fields: recipient_name, recipient_social, street to Text

Revision ID: extend_order_text_fields
Revises: add_calculator_prefs_to_user
Create Date: 2026-07-22
"""
import sqlalchemy as sa
from alembic import op

revision = 'extend_order_text_fields'
down_revision = 'add_calculator_prefs_to_user'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('order', 'recipient_name',
                    existing_type=sa.String(128),
                    type_=sa.String(255),
                    existing_nullable=False)
    op.alter_column('order', 'recipient_social',
                    existing_type=sa.String(128),
                    type_=sa.String(500),
                    existing_nullable=True)
    op.alter_column('order', 'street',
                    existing_type=sa.String(128),
                    type_=sa.String(500),
                    existing_nullable=False)


def downgrade():
    op.alter_column('order', 'street',
                    existing_type=sa.String(500),
                    type_=sa.String(128),
                    existing_nullable=False)
    op.alter_column('order', 'recipient_social',
                    existing_type=sa.String(500),
                    type_=sa.String(128),
                    existing_nullable=True)
    op.alter_column('order', 'recipient_name',
                    existing_type=sa.String(255),
                    type_=sa.String(128),
                    existing_nullable=False)
