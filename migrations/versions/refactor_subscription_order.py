"""Refactor: add Subscription model, update Order and Delivery tables

Revision ID: refactor_subscription_order
Revises: add_client_created_at
Create Date: 2026-03-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'refactor_subscription_order'
down_revision = 'add_client_created_at'
branch_labels = None
depends_on = None


def upgrade():
    # --- Create subscription table ---
    op.create_table(
        'subscription',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(32), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='active'),
        sa.Column('delivery_day', sa.String(16), nullable=False),
        sa.Column('time_from', sa.String(8), nullable=True),
        sa.Column('time_to', sa.String(8), nullable=True),
        sa.Column('recipient_name', sa.String(128), nullable=False),
        sa.Column('recipient_phone', sa.String(32), nullable=False),
        sa.Column('recipient_social', sa.String(128), nullable=True),
        sa.Column('city', sa.String(64), nullable=False),
        sa.Column('street', sa.String(128), nullable=False),
        sa.Column('building_number', sa.String(32), nullable=True),
        sa.Column('floor', sa.String(16), nullable=True),
        sa.Column('entrance', sa.String(16), nullable=True),
        sa.Column('is_pickup', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('address_comment', sa.Text(), nullable=True),
        sa.Column('delivery_method', sa.String(32), nullable=False, server_default='courier'),
        sa.Column('size', sa.String(32), nullable=False),
        sa.Column('custom_amount', sa.Integer(), nullable=True),
        sa.Column('bouquet_type', sa.String(64), nullable=True),
        sa.Column('composition_type', sa.String(64), nullable=True),
        sa.Column('for_whom', sa.String(64), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('preferences', sa.Text(), nullable=True),
        sa.Column('is_wedding', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_extended', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('followup_status', sa.String(32), nullable=True),
        sa.Column('followup_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['client.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # --- Update order table ---
    # Add new columns
    op.add_column('order', sa.Column('subscription_id', sa.Integer(), nullable=True))
    op.add_column('order', sa.Column('sequence_number', sa.Integer(), nullable=True))
    op.add_column('order', sa.Column('delivery_date', sa.Date(), nullable=True))

    # Copy data from first_delivery_date → delivery_date
    op.execute('UPDATE "order" SET delivery_date = first_delivery_date')

    # Make delivery_date non-nullable after populating
    op.alter_column('order', 'delivery_date', nullable=False)

    # Add FK constraint for subscription_id
    op.create_foreign_key(
        'fk_order_subscription_id',
        'order', 'subscription',
        ['subscription_id'], ['id']
    )

    # Drop obsolete columns
    op.drop_column('order', 'first_delivery_date')
    op.drop_column('order', 'delivery_type')
    op.drop_column('order', 'delivery_day')
    op.drop_column('order', 'bouquet_size')
    op.drop_column('order', 'price_at_order')
    op.drop_column('order', 'periodicity')
    op.drop_column('order', 'preferred_days')
    op.drop_column('order', 'is_subscription_extended')
    op.drop_column('order', 'subscription_followup_status')
    op.drop_column('order', 'subscription_followup_at')

    # --- Update delivery table ---
    op.drop_column('delivery', 'delivery_type')
    op.drop_column('delivery', 'is_subscription')
    op.drop_column('delivery', 'bouquet_size')


def downgrade():
    # Restore delivery columns
    op.add_column('delivery', sa.Column('bouquet_size', sa.String(16), nullable=True))
    op.add_column('delivery', sa.Column('is_subscription', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('delivery', sa.Column('delivery_type', sa.String(32), nullable=True))

    # Restore order columns
    op.add_column('order', sa.Column('subscription_followup_at', sa.DateTime(), nullable=True))
    op.add_column('order', sa.Column('subscription_followup_status', sa.String(32), nullable=True))
    op.add_column('order', sa.Column('is_subscription_extended', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('order', sa.Column('preferred_days', sa.String(64), nullable=True))
    op.add_column('order', sa.Column('periodicity', sa.String(8), nullable=True))
    op.add_column('order', sa.Column('price_at_order', sa.Integer(), nullable=True))
    op.add_column('order', sa.Column('bouquet_size', sa.String(16), nullable=True))
    op.add_column('order', sa.Column('delivery_day', sa.String(16), nullable=True))
    op.add_column('order', sa.Column('delivery_type', sa.String(32), nullable=True))
    op.add_column('order', sa.Column('first_delivery_date', sa.Date(), nullable=True))

    op.execute('UPDATE "order" SET first_delivery_date = delivery_date')
    op.alter_column('order', 'first_delivery_date', nullable=False)

    op.drop_constraint('fk_order_subscription_id', 'order', type_='foreignkey')
    op.drop_column('order', 'delivery_date')
    op.drop_column('order', 'sequence_number')
    op.drop_column('order', 'subscription_id')

    op.drop_table('subscription')
