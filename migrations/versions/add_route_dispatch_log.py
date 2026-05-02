"""Add route_dispatch_logs table

Revision ID: add_route_dispatch_log
Revises: add_florist_sale_payment_type, add_taxi_courier
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_route_dispatch_log'
down_revision = ('add_florist_sale_payment_type', 'add_taxi_courier')
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'route_dispatch_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('route_id', sa.Integer(), nullable=False),
        sa.Column('courier_id', sa.Integer(), nullable=True),
        sa.Column('sent_by_user_id', sa.Integer(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('message_text', sa.Text(), nullable=True),
        sa.Column('delivery_price', sa.Integer(), nullable=True),
        sa.Column('deliveries_count', sa.Integer(), nullable=True),
        sa.Column('total_distance_km', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['route_id'], ['delivery_routes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['courier_id'], ['courier.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sent_by_user_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_route_dispatch_logs_route_id', 'route_dispatch_logs', ['route_id'])


def downgrade():
    op.drop_index('ix_route_dispatch_logs_route_id', 'route_dispatch_logs')
    op.drop_table('route_dispatch_logs')
