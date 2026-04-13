"""Add name, phone_viber, phone_telegram, phone_whatsapp to client; make instagram nullable

Revision ID: add_client_contact_fields
Revises: add_discount_to_order_subscription
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_client_contact_fields'
down_revision = 'add_ai_agent_log'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('client', sa.Column('name', sa.String(128), nullable=True))
    op.add_column('client', sa.Column('phone_viber', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('client', sa.Column('phone_telegram', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('client', sa.Column('phone_whatsapp', sa.Boolean(), nullable=False, server_default='false'))
    op.alter_column('client', 'instagram', nullable=True)


def downgrade():
    op.alter_column('client', 'instagram', nullable=False)
    op.drop_column('client', 'phone_whatsapp')
    op.drop_column('client', 'phone_telegram')
    op.drop_column('client', 'phone_viber')
    op.drop_column('client', 'name')
