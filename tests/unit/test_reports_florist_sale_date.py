"""Offline florist sales report by the linked transaction's date.

Regression: an offline sale is created on day X, then an admin edits the linked
'Офлайн продаж' transaction and moves its date to the previous month. Both the
P&L revenue and the florist-bonus report must follow the transaction date, not
the immutable FloristSale.created_at audit timestamp.
"""
import datetime
from decimal import Decimal

from app.models.user import User
from app.models.transaction import Transaction
from app.models.florist_sale import FloristSale
from app.services.reports_service import get_pl_data, get_florist_sales_data


def _florist(session):
    u = User(username='florist_x', email='florist_x@example.com')
    u.set_password('x')
    session.add(u)
    session.flush()
    return u


def _offline_sale(session, florist, amount, txn_date):
    amount = Decimal(str(amount))
    txn = Transaction(
        transaction_type='credit', client_id=None, amount=float(amount),
        payment_type='cash', comment='Офлайн продаж', date=txn_date,
        created_by_id=florist.id,
    )
    session.add(txn)
    session.flush()
    sale = FloristSale(
        florist_id=florist.id, created_by=florist.id, amount=amount,
        bonus_percent=Decimal('5.0'),
        bonus_amount=(amount * Decimal('5.0') / Decimal('100')).quantize(Decimal('0.01')),
        payment_type='cash', transaction_id=txn.id,
    )
    session.add(sale)
    session.commit()
    return sale, txn


def test_florist_sale_follows_transaction_date_after_edit(app, session):
    florist = _florist(session)
    # created "now" (Sep), but the transaction is dated Aug 31
    sale, txn = _offline_sale(session, florist, 1000, datetime.date(2026, 8, 31))

    aug_from, aug_to = '2026-08-01', '2026-08-31'
    sep_from, sep_to = '2026-09-01', '2026-09-30'

    # August: counted in both revenue and florist bonus
    assert get_pl_data(aug_from, aug_to)['revenue'] == 1000
    aug_florist = get_florist_sales_data(aug_from, aug_to)
    assert aug_florist['grand_total'] == 1000
    assert aug_florist['grand_bonus'] == 50

    # September: not there anymore
    assert get_pl_data(sep_from, sep_to)['revenue'] == 0
    assert get_florist_sales_data(sep_from, sep_to)['grand_total'] == 0


def test_legacy_sale_without_transaction_falls_back_to_created_at(app, session):
    florist = _florist(session)
    sale = FloristSale(
        florist_id=florist.id, created_by=florist.id, amount=Decimal('500'),
        bonus_percent=Decimal('5.0'), bonus_amount=Decimal('25.00'),
        payment_type='cash', transaction_id=None,
    )
    session.add(sale)
    session.commit()

    today = datetime.date.today()
    d_from = today.replace(day=1).isoformat()
    d_to = today.isoformat()
    assert get_florist_sales_data(d_from, d_to)['grand_total'] == 500
