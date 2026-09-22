"""Add quick_reply table

Canned responses managers can insert into the /inbox composer.

Revision ID: add_quick_reply
Revises: add_message_reply_to
Create Date: 2026-09-22 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op


revision = 'add_quick_reply'
down_revision = 'add_message_reply_to'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'quick_reply',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Integer(),
                 sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table('quick_reply')
