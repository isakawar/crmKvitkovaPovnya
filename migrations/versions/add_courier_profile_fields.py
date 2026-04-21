"""Add courier profile fields

Revision ID: add_courier_profile_fields
Revises: add_taxi_courier
Create Date: 2026-04-21

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_courier_profile_fields'
down_revision = 'add_display_name_to_user'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('courier', sa.Column('communication_channel', sa.String(20), nullable=True))
    op.add_column('courier', sa.Column('nickname', sa.String(64), nullable=True))
    op.add_column('courier', sa.Column('working_days', sa.String(50), nullable=True))
    op.add_column('courier', sa.Column('comment', sa.Text(), nullable=True))
    op.add_column('courier', sa.Column('rating', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('courier', 'rating')
    op.drop_column('courier', 'comment')
    op.drop_column('courier', 'working_days')
    op.drop_column('courier', 'nickname')
    op.drop_column('courier', 'communication_channel')
