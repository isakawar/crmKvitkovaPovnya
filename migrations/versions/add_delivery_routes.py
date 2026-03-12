"""Add delivery_routes and route_deliveries tables

Revision ID: add_delivery_routes
Revises: initial_postgresql
Create Date: 2026-03-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_delivery_routes'
down_revision = 'initial_postgresql'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('delivery_routes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('courier_id', sa.Integer(), nullable=True),
        sa.Column('route_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('delivery_price', sa.Integer(), nullable=True),
        sa.Column('deliveries_count', sa.Integer(), nullable=True),
        sa.Column('total_distance_km', sa.Float(), nullable=True),
        sa.Column('estimated_duration_min', sa.Integer(), nullable=True),
        sa.Column('telegram_message_id', sa.BigInteger(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('rejected_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['courier_id'], ['courier.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('route_deliveries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('route_id', sa.Integer(), nullable=False),
        sa.Column('delivery_id', sa.Integer(), nullable=False),
        sa.Column('stop_order', sa.Integer(), nullable=False),
        sa.Column('distance_from_previous_km', sa.Float(), nullable=True),
        sa.Column('duration_from_previous_min', sa.Integer(), nullable=True),
        sa.Column('planned_arrival', sa.DateTime(), nullable=True),
        sa.Column('actual_arrival', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['delivery_id'], ['delivery.id'], ),
        sa.ForeignKeyConstraint(['route_id'], ['delivery_routes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('route_deliveries')
    op.drop_table('delivery_routes')
