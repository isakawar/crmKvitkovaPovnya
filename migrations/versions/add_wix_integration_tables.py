"""Add wix_lead and wix_product_mapping tables

Revision ID: add_wix_integration_tables
Revises: add_promo_codes
Create Date: 2026-08-24
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_wix_integration_tables'
down_revision = 'add_promo_codes'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'wix_product_mapping',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('catalog_item_id', sa.String(length=64), nullable=False),
        sa.Column('wix_item_name', sa.String(length=255), nullable=True),
        sa.Column('order_scenario', sa.String(length=16), nullable=False),
        sa.Column('delivery_type', sa.String(length=32), nullable=True),
        sa.Column('size', sa.String(length=32), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('catalog_item_id'),
    )
    op.create_index(
        'ix_wix_product_mapping_catalog_item_id', 'wix_product_mapping', ['catalog_item_id']
    )

    op.create_table(
        'wix_lead',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('wix_order_id', sa.String(length=64), nullable=False),
        sa.Column('wix_order_number', sa.String(length=32), nullable=True),
        sa.Column('raw_payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='new'),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=32), nullable=True),
        sa.Column('contact_email', sa.String(length=256), nullable=True),
        sa.Column('city', sa.String(length=128), nullable=True),
        sa.Column('street', sa.String(length=500), nullable=True),
        sa.Column('postal_code', sa.String(length=16), nullable=True),
        sa.Column('address_comment', sa.Text(), nullable=True),
        sa.Column('item_name', sa.String(length=255), nullable=True),
        sa.Column('catalog_item_id', sa.String(length=64), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('currency', sa.String(length=8), nullable=True),
        sa.Column('payment_status', sa.String(length=32), nullable=True),
        sa.Column('line_items_count', sa.Integer(), nullable=True),
        sa.Column('matched_client_id', sa.Integer(), nullable=True),
        sa.Column('mapping_matched', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('processed_order_id', sa.Integer(), nullable=True),
        sa.Column('processed_subscription_id', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('processed_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['matched_client_id'], ['client.id']),
        sa.ForeignKeyConstraint(['processed_order_id'], ['order.id']),
        sa.ForeignKeyConstraint(['processed_subscription_id'], ['subscription.id']),
        sa.ForeignKeyConstraint(['processed_by_user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('wix_order_id'),
    )
    op.create_index('ix_wix_lead_wix_order_id', 'wix_lead', ['wix_order_id'])
    op.create_index('ix_wix_lead_catalog_item_id', 'wix_lead', ['catalog_item_id'])


def downgrade():
    op.drop_index('ix_wix_lead_catalog_item_id', table_name='wix_lead')
    op.drop_index('ix_wix_lead_wix_order_id', table_name='wix_lead')
    op.drop_table('wix_lead')
    op.drop_index('ix_wix_product_mapping_catalog_item_id', table_name='wix_product_mapping')
    op.drop_table('wix_product_mapping')
