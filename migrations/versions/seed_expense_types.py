"""seed expense types into settings

Revision ID: seed_expense_types
Revises: merge_heads_before_expense_types
Create Date: 2026-05-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

revision = 'seed_expense_types'
down_revision = 'merge_heads_before_expense_types'
branch_labels = None
depends_on = None

EXPENSE_TYPES = [
    'Квіти',
    'Залишки квітів',
    'Пакування',
    'Вази',
    'Ножиці',
    'Доставка',
    'Доставка квітів',
    'Підживлення для квітів',
    'реклама Facebook',
    'Реклама (блогери)',
    'сервіси',
    'Тестові букети',
    'рекламні букети',
    'букет комплімент',
    'Нова пошта',
    'Іжа та напої',
    'Інші витрати',
    'оренда офісу',
    'комунальні',
    'інтернет',
    'Меблі та інше',
    'Амортизація',
    'Клінінг',
    'Флорист №1 (Аня)',
    'Флорист №2 (Наталя)',
    'ТікТок (Наталі)',
    'Client Manager (Паханчік)',
    'SMM',
    'Таргетолог',
    'Еквайрінг',
    'Податок',
]

settings_table = table(
    'settings',
    column('type', sa.String),
    column('value', sa.String),
)


def upgrade():
    conn = op.get_bind()
    existing = {row[0] for row in conn.execute(
        sa.text("SELECT value FROM settings WHERE type = 'expense_type'")
    )}
    rows = [{'type': 'expense_type', 'value': v} for v in EXPENSE_TYPES if v not in existing]
    if rows:
        op.bulk_insert(settings_table, rows)


def downgrade():
    op.execute("DELETE FROM settings WHERE type = 'expense_type'")
