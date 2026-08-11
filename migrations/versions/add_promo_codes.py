"""Add promo_codes table and promo_code_id on order/subscription

Revision ID: add_promo_codes
Revises: extend_order_text_fields
Create Date: 2026-07-23
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_promo_codes'
down_revision = 'extend_order_text_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'promo_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('discount_percent', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    op.add_column('order', sa.Column('promo_code_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_order_promo_code_id', 'order', 'promo_codes', ['promo_code_id'], ['id'])

    op.add_column('subscription', sa.Column('promo_code_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_subscription_promo_code_id', 'subscription', 'promo_codes', ['promo_code_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_subscription_promo_code_id', 'subscription', type_='foreignkey')
    op.drop_column('subscription', 'promo_code_id')

    op.drop_constraint('fk_order_promo_code_id', 'order', type_='foreignkey')
    op.drop_column('order', 'promo_code_id')

    op.drop_table('promo_codes')
