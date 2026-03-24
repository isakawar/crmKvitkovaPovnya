"""Add performance indexes on key columns

Revision ID: add_performance_indexes
Revises: refactor_subscription_order
Create Date: 2026-03-24 00:00:00.000000

"""
from alembic import op


revision = 'add_performance_indexes'
down_revision = 'refactor_subscription_order'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_delivery_delivery_date', 'delivery', ['delivery_date'])
    op.create_index('ix_delivery_status', 'delivery', ['status'])
    op.create_index('ix_delivery_courier_id', 'delivery', ['courier_id'])
    op.create_index('ix_delivery_order_id', 'delivery', ['order_id'])
    op.create_index('ix_delivery_client_id', 'delivery', ['client_id'])
    op.create_index('ix_order_client_id', 'order', ['client_id'])
    op.create_index('ix_order_subscription_id', 'order', ['subscription_id'])
    op.create_index('ix_client_instagram', 'client', ['instagram'])
    op.create_index('ix_certificates_status', 'certificates', ['status'])


def downgrade():
    op.drop_index('ix_certificates_status', 'certificates')
    op.drop_index('ix_client_instagram', 'client')
    op.drop_index('ix_order_subscription_id', 'order')
    op.drop_index('ix_order_client_id', 'order')
    op.drop_index('ix_delivery_client_id', 'delivery')
    op.drop_index('ix_delivery_order_id', 'delivery')
    op.drop_index('ix_delivery_courier_id', 'delivery')
    op.drop_index('ix_delivery_status', 'delivery')
    op.drop_index('ix_delivery_delivery_date', 'delivery')
