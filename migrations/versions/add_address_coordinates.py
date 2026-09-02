"""Add Google-resolved address coordinates to subscription / order / delivery

latitude, longitude, google_place_id and formatted_address are populated when a
manager picks an address from the Google Places autocomplete in the order /
subscription forms. Coordinates are forwarded to the route optimizer so it does
not have to geocode the address string again.

Revision ID: add_address_coordinates
Revises: add_wix_lead_custom_fields
Create Date: 2026-09-01
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_address_coordinates'
down_revision = 'add_wix_lead_custom_fields'
branch_labels = None
depends_on = None

_TABLES = ('subscription', 'order', 'delivery')


def upgrade():
    for table in _TABLES:
        op.add_column(table, sa.Column('latitude', sa.Numeric(9, 6), nullable=True))
        op.add_column(table, sa.Column('longitude', sa.Numeric(9, 6), nullable=True))
        op.add_column(table, sa.Column('google_place_id', sa.String(255), nullable=True))
        op.add_column(table, sa.Column('formatted_address', sa.String(500), nullable=True))


def downgrade():
    for table in _TABLES:
        op.drop_column(table, 'formatted_address')
        op.drop_column(table, 'google_place_id')
        op.drop_column(table, 'longitude')
        op.drop_column(table, 'latitude')
