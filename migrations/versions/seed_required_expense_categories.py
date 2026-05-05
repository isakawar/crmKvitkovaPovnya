"""seed required expense categories (delivery, salary, flowers)

These three categories are mandatory — they drive P&L metrics in reports_service.py.
DO NOT delete them from the database.

Revision ID: seed_required_expense_categories
Revises: add_expense_category
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = 'seed_required_expense_categories'
down_revision = 'add_expense_category'
branch_labels = None
depends_on = None

REQUIRED_CATEGORIES = [
    {'slug': 'delivery', 'name': 'Доставка'},
    {'slug': 'salary',   'name': 'Зарплата'},
    {'slug': 'flowers',  'name': 'Квіти'},
]

def upgrade():
    for cat in REQUIRED_CATEGORIES:
        op.execute(
            sa.text(
                "INSERT INTO expense_category (name, slug) "
                "VALUES (:name, :slug) "
                "ON CONFLICT DO NOTHING"
            ).bindparams(name=cat['name'], slug=cat['slug'])
        )


def downgrade():
    for cat in REQUIRED_CATEGORIES:
        op.execute(
            sa.text("DELETE FROM expense_category WHERE slug = :slug").bindparams(slug=cat['slug'])
        )
