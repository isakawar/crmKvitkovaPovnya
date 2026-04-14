"""Add taxi courier support

Revision ID: add_taxi_courier
Revises: add_email_to_client
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_taxi_courier'
down_revision = 'add_sub_delivery_count'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('courier', sa.Column('is_taxi', sa.Boolean(), nullable=False,
                                       server_default=sa.text('false')))
    op.alter_column('courier', 'phone', nullable=True)


def downgrade():
    # Safety: fill NULLs before restoring NOT NULL constraint
    op.execute("UPDATE courier SET phone = '' WHERE phone IS NULL")
    op.alter_column('courier', 'phone', nullable=False)
    op.drop_column('courier', 'is_taxi')
