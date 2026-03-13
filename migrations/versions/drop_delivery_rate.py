"""Drop delivery_rate column from courier table

Revision ID: drop_delivery_rate
Revises: add_delivery_method
Create Date: 2026-03-13 00:00:00.000000

"""
from alembic import op

revision = 'drop_delivery_rate'
down_revision = 'add_delivery_method'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('courier', 'delivery_rate')


def downgrade():
    import sqlalchemy as sa
    op.add_column('courier', sa.Column('delivery_rate', sa.Integer(), nullable=True, server_default='50'))
