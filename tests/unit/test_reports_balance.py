"""get_client_revenue_breakdown — помісячний баланс клієнтів.

Найскладніша функція проєкту і до цього моменту повністю непокрита. Особливість,
через яку вона варта окремого файлу: історія НЕ зберігається, а виводиться назад
від поточного ``client.credits``:

    balance_start = credits - (усе сплачене від d_from) + (усе списане від d_from)

потім прохід уперед по місяцях. Наслідок — якщо ``client.credits`` розійдеться з
транзакціями хоч на гривню, поїде не один рядок, а ВСЯ показана історія, мовчки
й заднім числом. Тому головний інваріант тут не «цифра в клітинці правильна», а
**замикання**: останній balance_end має зійтися з client.credits.
"""
import datetime
from decimal import Decimal

from app.extensions import db
from app.models import Client, Order, Delivery
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.constants import (
    TXN_ADJUSTMENT,
    TXN_CREDIT,
    TXN_DELIVERY_CHARGE,
    SUBSCRIPTION_ACTIVE,
)
from app.services.reports_service import get_client_revenue_breakdown


MONTH_A = datetime.date(2026, 5, 1)
MONTH_B = datetime.date(2026, 6, 1)
MONTH_C = datetime.date(2026, 7, 1)
RANGE = ('2026-05-01', '2026-07-31')


def _client(session, handle, credits=0):
    c = Client(instagram=handle, credits=Decimal(credits))
    session.add(c)
    session.commit()
    return c


def _subscription(session, client):
    sub = Subscription(
        client_id=client.id, type='Weekly', status=SUBSCRIPTION_ACTIVE, delivery_day='ПН',
        recipient_name='Отримувач', recipient_phone='+380991234567',
        city='Київ', street='Хрещатик 1', size='M', for_whom='Дружина',
    )
    session.add(sub)
    session.commit()
    return sub


def _delivery(session, client, when, subscription=None):
    order = Order(
        client_id=client.id,
        subscription_id=subscription.id if subscription else None,
        recipient_name='Отримувач', recipient_phone='+380991234567',
        city='Київ', street='Хрещатик 1', is_pickup=False, delivery_method='courier',
        size='M', delivery_date=when, for_whom='Дружина',
    )
    session.add(order)
    session.flush()
    delivery = Delivery(
        order_id=order.id, client_id=client.id, delivery_date=when,
        status='Доставлено', size='M', phone='+380991234567', delivery_method='courier',
    )
    session.add(delivery)
    session.commit()
    return delivery


def _txn(session, client, kind, amount, when, delivery=None):
    """Створити транзакцію І зрушити credits так само, як це робить білінг."""
    t = Transaction(
        transaction_type=kind, client_id=client.id, amount=Decimal(amount),
        date=when, delivery_id=delivery.id if delivery else None,
    )
    session.add(t)
    sign = -1 if kind == TXN_DELIVERY_CHARGE else 1
    client.credits = (client.credits or Decimal(0)) + sign * Decimal(amount)
    session.commit()
    return t


def _row_for(result, client):
    for row in result['rows']:
        if row['client'].id == client.id:
            return row
    raise AssertionError(f'клієнта {client.instagram} немає у звіті')


# ── Головний інваріант: замикання на client.credits ───────────────────────────

def test_last_month_balance_closes_on_client_credits(app, session):
    """Якщо діапазон покриває всі транзакції, останній balance_end == credits.

    Це і є та властивість, яка ламається при будь-якому розсинхроні балансу.
    """
    client = _client(session, 'bal_close')
    sub = _subscription(session, client)

    d1 = _delivery(session, client, datetime.date(2026, 5, 12), sub)
    _txn(session, client, TXN_DELIVERY_CHARGE, 1000, datetime.date(2026, 5, 12), d1)
    _txn(session, client, TXN_CREDIT, 4000, datetime.date(2026, 5, 20))
    d2 = _delivery(session, client, datetime.date(2026, 6, 9), sub)
    _txn(session, client, TXN_DELIVERY_CHARGE, 1000, datetime.date(2026, 6, 9), d2)

    result = get_client_revenue_breakdown(*RANGE)
    row = _row_for(result, client)

    assert client.credits == Decimal(2000)
    assert row['months'][MONTH_C]['balance_end'] == 2000


def test_months_form_a_continuous_chain(app, session):
    """balance_start кожного місяця == balance_end попереднього."""
    client = _client(session, 'bal_chain')
    sub = _subscription(session, client)

    _txn(session, client, TXN_CREDIT, 5000, datetime.date(2026, 5, 3))
    for when in (datetime.date(2026, 5, 12), datetime.date(2026, 6, 9), datetime.date(2026, 7, 7)):
        d = _delivery(session, client, when, sub)
        _txn(session, client, TXN_DELIVERY_CHARGE, 1000, when, d)

    months = get_client_revenue_breakdown(*RANGE)
    row = _row_for(months, client)['months']

    assert row[MONTH_B]['balance_start'] == row[MONTH_A]['balance_end']
    assert row[MONTH_C]['balance_start'] == row[MONTH_B]['balance_end']


def test_balance_end_is_start_plus_paid_minus_charged(app, session):
    client = _client(session, 'bal_formula')
    sub = _subscription(session, client)
    _txn(session, client, TXN_CREDIT, 3000, datetime.date(2026, 5, 3))
    d = _delivery(session, client, datetime.date(2026, 5, 12), sub)
    _txn(session, client, TXN_DELIVERY_CHARGE, 1000, datetime.date(2026, 5, 12), d)

    row = _row_for(get_client_revenue_breakdown(*RANGE), client)['months'][MONTH_A]

    assert row['paid'] == 3000
    assert row['charged'] == 1000
    assert row['balance_end'] == row['balance_start'] + row['paid'] + row['adj'] - row['charged']


# ── Розкладка по місяцях ──────────────────────────────────────────────────────

def test_amounts_land_in_the_month_of_the_transaction_date(app, session):
    client = _client(session, 'bal_months')
    sub = _subscription(session, client)
    d_may = _delivery(session, client, datetime.date(2026, 5, 31), sub)
    _txn(session, client, TXN_DELIVERY_CHARGE, 700, datetime.date(2026, 5, 31), d_may)
    d_jun = _delivery(session, client, datetime.date(2026, 6, 1), sub)
    _txn(session, client, TXN_DELIVERY_CHARGE, 900, datetime.date(2026, 6, 1), d_jun)

    row = _row_for(get_client_revenue_breakdown(*RANGE), client)['months']

    assert row[MONTH_A]['charged'] == 700
    assert row[MONTH_B]['charged'] == 900
    assert row[MONTH_C]['charged'] == 0


# ── Сторно ────────────────────────────────────────────────────────────────────

def test_reversal_nets_out_charged_within_its_month(app, session):
    """Сторно — відʼємний delivery_charge, тож звіт занулює його сам, без спецкоду."""
    client = _client(session, 'bal_reversal')
    sub = _subscription(session, client)
    d = _delivery(session, client, datetime.date(2026, 6, 9), sub)
    _txn(session, client, TXN_DELIVERY_CHARGE, 1000, datetime.date(2026, 6, 9), d)
    _txn(session, client, TXN_DELIVERY_CHARGE, -1000, datetime.date(2026, 6, 20), d)

    row = _row_for(get_client_revenue_breakdown(*RANGE), client)['months']

    assert row[MONTH_B]['charged'] == 0
    assert client.credits == Decimal(0)


def test_reversal_in_a_later_month_leaves_the_original_month_intact(app, session):
    """Сторно проводиться поточною датою — закритий місяць не переписується."""
    client = _client(session, 'bal_reversal_late')
    sub = _subscription(session, client)
    d = _delivery(session, client, datetime.date(2026, 5, 12), sub)
    _txn(session, client, TXN_DELIVERY_CHARGE, 1000, datetime.date(2026, 5, 12), d)
    _txn(session, client, TXN_DELIVERY_CHARGE, -1000, datetime.date(2026, 7, 2), d)

    row = _row_for(get_client_revenue_breakdown(*RANGE), client)['months']

    assert row[MONTH_A]['charged'] == 1000      # травень лишився як був
    assert row[MONTH_C]['charged'] == -1000     # компенсація видна в липні
    assert row[MONTH_C]['balance_end'] == 0


# ── Ручне коригування ─────────────────────────────────────────────────────────

def test_adjustment_shows_separately_and_moves_the_balance(app, session):
    client = _client(session, 'bal_adj')
    sub = _subscription(session, client)
    d = _delivery(session, client, datetime.date(2026, 6, 9), sub)
    _txn(session, client, TXN_DELIVERY_CHARGE, 1000, datetime.date(2026, 6, 9), d)
    _txn(session, client, TXN_ADJUSTMENT, 250, datetime.date(2026, 6, 15))

    row = _row_for(get_client_revenue_breakdown(*RANGE), client)['months']

    # Коригування не змішується з оплатами — воно в окремій колонці
    assert row[MONTH_B]['adj'] == 250
    assert row[MONTH_B]['paid'] == 0
    assert row[MONTH_B]['balance_end'] == row[MONTH_B]['balance_start'] + 250 - 1000
    assert row[MONTH_C]['balance_end'] == client.credits


# ── Розділення разових і підписочних нарахувань ───────────────────────────────

def test_one_time_and_subscription_charges_are_tracked_separately(app, session):
    """Нарахування розкладаються по (клієнт, підписка|None), але баланс клієнтський."""
    client = _client(session, 'bal_split')
    sub = _subscription(session, client)
    d_sub = _delivery(session, client, datetime.date(2026, 6, 9), sub)
    _txn(session, client, TXN_DELIVERY_CHARGE, 1000, datetime.date(2026, 6, 9), d_sub)
    d_one = _delivery(session, client, datetime.date(2026, 6, 10), None)
    _txn(session, client, TXN_DELIVERY_CHARGE, 1500, datetime.date(2026, 6, 10), d_one)

    row = _row_for(get_client_revenue_breakdown(*RANGE), client)['months']

    # На рівні клієнта — сума обох
    assert row[MONTH_B]['charged'] == 2500
    assert row[MONTH_C]['balance_end'] == client.credits


def test_unlinked_charge_is_counted_as_one_time(app, session):
    """Ручне нарахування без delivery_id (коригування нарахувань) не губиться."""
    client = _client(session, 'bal_unlinked')
    _subscription(session, client)
    _txn(session, client, TXN_DELIVERY_CHARGE, 333, datetime.date(2026, 6, 4))

    row = _row_for(get_client_revenue_breakdown(*RANGE), client)['months']

    assert row[MONTH_B]['charged'] == 333


# ── Позначка активності ───────────────────────────────────────────────────────

def test_client_with_no_operations_in_range_is_flagged_inactive(app, session):
    client = _client(session, 'bal_quiet')
    _subscription(session, client)

    row = _row_for(get_client_revenue_breakdown(*RANGE), client)

    assert row['any_activity'] is False
    assert all(row['months'][mo]['charged'] == 0 for mo in (MONTH_A, MONTH_B, MONTH_C))


def test_totals_sum_across_clients(app, session):
    a = _client(session, 'bal_tot_a')
    b = _client(session, 'bal_tot_b')
    for client, amount in ((a, 1000), (b, 400)):
        sub = _subscription(session, client)
        d = _delivery(session, client, datetime.date(2026, 6, 9), sub)
        _txn(session, client, TXN_DELIVERY_CHARGE, amount, datetime.date(2026, 6, 9), d)
        _txn(session, client, TXN_CREDIT, amount, datetime.date(2026, 6, 10))

    result = get_client_revenue_breakdown(*RANGE)

    assert result['totals'][MONTH_B]['charged'] == 1400
    assert result['totals'][MONTH_B]['paid'] == 1400
