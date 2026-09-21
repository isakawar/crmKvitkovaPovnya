"""Індекси для транзакцій, підписок і фільтрів звітів.

Таблиця `transaction` не мала ЖОДНОГО індексу, хоча сторінка /reports б'є по ній
15+ разів за один рендер, майже завжди у формі
`WHERE transaction_type = ? AND date BETWEEN ? AND ?`. Таблиця `subscription`
так само не мала жодного, включно з client_id, по якому йде join у звіті
«Баланс клієнтів» і в черзі продовжень.

Попередня міграція add_performance_indexes покрила `order` і `delivery`, але ці
дві таблиці пропустила.

Індекс по lower(instagram)/lower(telegram) — для дедуплікації клієнтів:
_validate_contact_fields шукає через func.lower(), а звичайний btree по колонці
для цього не годиться, тож кожне створення клієнта робило seq scan.

Таблиці невеликі, тож звичайний CREATE INDEX (без CONCURRENTLY) відпрацює за
секунди; окремої транзакції він не потребує.

Revision ID: add_billing_performance_indexes
Revises: add_messaging_message_indexes
"""
import sqlalchemy as sa
from alembic import op

revision = 'add_billing_performance_indexes'
down_revision = 'add_messaging_message_indexes'
branch_labels = None
depends_on = None


def upgrade():
    # ── transaction: жодного індексу до цього моменту ─────────────────────────
    # Основний патерн звітів — фільтр за типом + діапазоном дат.
    op.create_index('ix_transaction_type_date', 'transaction', ['transaction_type', 'date'])
    # Список транзакцій фільтрує тільки за датою.
    op.create_index('ix_transaction_date', 'transaction', ['date'])
    op.create_index('ix_transaction_client_id', 'transaction', ['client_id'])
    # net_charged_for_delivery і get_charges_data ходять саме сюди.
    op.create_index('ix_transaction_delivery_id', 'transaction', ['delivery_id'])
    op.create_index('ix_transaction_subscription_id', 'transaction', ['subscription_id'])
    op.create_index('ix_transaction_payment_account_id', 'transaction', ['payment_account_id'])

    # ── subscription: теж жодного ─────────────────────────────────────────────
    op.create_index('ix_subscription_client_id', 'subscription', ['client_id'])
    op.create_index('ix_subscription_status', 'subscription', ['status'])

    # ── order: фільтри звітів ─────────────────────────────────────────────────
    # get_orders_data фільтрує всі breakdown-и за created_at.
    op.create_index('ix_order_created_at', 'order', ['created_at'])
    op.create_index('ix_order_delivery_date', 'order', ['delivery_date'])

    # ── client: пошук і дедуплікація ──────────────────────────────────────────
    op.create_index('ix_client_phone', 'client', ['phone'])
    op.create_index('ix_client_instagram_lower', 'client', [sa.text('lower(instagram)')])
    op.create_index('ix_client_telegram_lower', 'client', [sa.text('lower(telegram)')])

    # ── route_deliveries: чиститься за delivery_id у 4 місцях ─────────────────
    op.create_index('ix_route_deliveries_delivery_id', 'route_deliveries', ['delivery_id'])
    op.create_index('ix_route_deliveries_route_id', 'route_deliveries', ['route_id'])


def downgrade():
    op.drop_index('ix_route_deliveries_route_id', table_name='route_deliveries')
    op.drop_index('ix_route_deliveries_delivery_id', table_name='route_deliveries')

    op.drop_index('ix_client_telegram_lower', table_name='client')
    op.drop_index('ix_client_instagram_lower', table_name='client')
    op.drop_index('ix_client_phone', table_name='client')

    op.drop_index('ix_order_delivery_date', table_name='order')
    op.drop_index('ix_order_created_at', table_name='order')

    op.drop_index('ix_subscription_status', table_name='subscription')
    op.drop_index('ix_subscription_client_id', table_name='subscription')

    op.drop_index('ix_transaction_payment_account_id', table_name='transaction')
    op.drop_index('ix_transaction_subscription_id', table_name='transaction')
    op.drop_index('ix_transaction_delivery_id', table_name='transaction')
    op.drop_index('ix_transaction_client_id', table_name='transaction')
    op.drop_index('ix_transaction_date', table_name='transaction')
    op.drop_index('ix_transaction_type_date', table_name='transaction')
