"""Add buyer_note + custom_fields to wix_lead

Checkout custom fields ("Періодичність доставки", "Дата першої доставки",
"Побажання", ...) and the buyer note are not present in the Wix "order placed"
automation payload. They are fetched from the Wix Orders API and stored here.

Revision ID: add_wix_lead_custom_fields
Revises: merge_wix_txn_target
Create Date: 2026-08-31
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_wix_lead_custom_fields'
down_revision = 'merge_wix_txn_target'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('wix_lead', sa.Column('buyer_note', sa.Text(), nullable=True))
    op.add_column('wix_lead', sa.Column('custom_fields', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('wix_lead', 'custom_fields')
    op.drop_column('wix_lead', 'buyer_note')
