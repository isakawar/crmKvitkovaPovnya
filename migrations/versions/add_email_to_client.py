"""Add email to client

Revision ID: add_email_to_client
Revises: add_client_contact_fields
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_email_to_client'
down_revision = 'add_client_contact_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('client', sa.Column('email', sa.String(256), nullable=True))


def downgrade():
    op.drop_column('client', 'email')
