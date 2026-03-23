"""Add certificates table

Revision ID: add_certificates_table
Revises: add_route_cache
Create Date: 2026-03-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_certificates_table'
down_revision = 'add_route_cache'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'certificates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('value_amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('value_size', sa.String(length=10), nullable=True),
        sa.Column('subscription_type', sa.String(length=20), nullable=True),
        sa.Column('expires_at', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['order.id'], name='fk_certificates_order_id'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], name='fk_certificates_created_by_user_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_certificates_code'),
    )


def downgrade():
    op.drop_table('certificates')
