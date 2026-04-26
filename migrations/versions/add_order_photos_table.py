"""add order_photos table

Revision ID: add_order_photos_table
Revises: rename_followup_at
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_order_photos_table'
down_revision = 'rename_followup_at'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'order_photos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('order.id'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_name', sa.String(255), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('comment', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_order_photos_order_id', 'order_photos', ['order_id'])


def downgrade():
    op.drop_index('ix_order_photos_order_id', table_name='order_photos')
    op.drop_table('order_photos')
