"""Бізнес-правила, підтверджені власником магазину (2026-09-22).

Ці тести закріплюють ДОМОВЛЕНОСТІ, а не поведінку коду. Якщо якийсь із них
почервонів — спершу спитай власника, чи змінилось правило, і лише потім правь
тест. Мовчки підганяти очікування під новий код тут не можна: саме так
неправильне правило стає «офіційним».

Підтверджено:
  * ціна за одну доставку підписки = ціна циклу ÷ 4 ЗАВЖДИ, навіть якщо
    delivery_count інший (6 доставок коштують 6 × (ціна ÷ 4), а не ціну циклу);
  * автознижка за лояльність: 0 → 5% → 10%, і 10% — стеля, скільки б продовжень
    не було; вручну виставлену вищу знижку автоматика не знижує;
  * мінімальний проміжок при переносі: 4 дні (Weekly), 9 днів (Bi-weekly);
  * фінансовий тиждень: субота → пʼятниця включно.
"""
import datetime

import pytest

from app.models import Client, Order, Delivery
from app.models.price import Price
from app.models.price_preset import PricePreset
from app.models.settings import Settings
from app.models.subscription import Subscription
from app.services.billing_service import get_order_price, reconcile_historical_charges
from app.services.delivery_service import get_financial_week_dates
from app.services.subscription_service import (
    BIWEEKLY_MIN_GAP_DAYS,
    WEEKLY_MIN_GAP_DAYS,
    _get_first_valid_date,
    create_subscription,
    extend_subscription,
)
from app.models.transaction import Transaction


CYCLE_PRICE = 4000          # ціна циклу підписки для розміру M
ONE_TIME_PRICE = 1200


def _seed_preset(session, size_value='M'):
    size = Settings(type='size', value=size_value)
    session.add(size)
    session.flush()
    preset = PricePreset(name='Основний', is_active=True)
    session.add(preset)
    session.flush()
    session.add(Price(preset_id=preset.id, order_type='one_time',
                      size_id=size.id, price=ONE_TIME_PRICE))
    session.add(Price(preset_id=preset.id, order_type='subscription',
                      size_id=size.id, price=CYCLE_PRICE))
    session.commit()
    return preset, size


def _client(session, handle, personal_discount=None):
    c = Client(instagram=handle, personal_discount=personal_discount)
    session.add(c)
    session.commit()
    return c


def _order(session, client, *, subscription=None, size='M', discount=None, custom_amount=None):
    o = Order(
        client_id=client.id,
        subscription_id=subscription.id if subscription else None,
        recipient_name='Отримувач', recipient_phone='+380991234567',
        city='Київ', street='Хрещатик 1', is_pickup=False, delivery_method='courier',
        size=size, custom_amount=custom_amount, discount=discount,
        delivery_date=datetime.date.today(), for_whom='Дружина',
    )
    session.add(o)
    session.commit()
    return o


def _sub_form(**over):
    form = {
        'delivery_type': 'Weekly', 'delivery_day': 'ПН',
        'first_delivery_date': datetime.date.today().isoformat(),
        'recipient_name': 'Отримувач', 'recipient_phone': '+380991234567',
        'city': 'Київ', 'street': 'Хрещатик 1', 'size': 'M', 'for_whom': 'Дружина',
    }
    form.update(over)
    return form


# ── Ціна: цикл ÷ 4 завжди ─────────────────────────────────────────────────────

def test_subscription_delivery_costs_a_quarter_of_the_cycle_price(app, session):
    _seed_preset(session)
    client = _client(session, 'price_sub')
    sub = Subscription(
        client_id=client.id, type='Weekly', status='active', delivery_day='ПН',
        recipient_name='О', recipient_phone='+380991234567',
        city='Київ', street='х', size='M', for_whom='Д',
    )
    session.add(sub)
    session.commit()

    assert get_order_price(_order(session, client, subscription=sub)) == CYCLE_PRICE // 4


@pytest.mark.parametrize('delivery_count', [4, 6, 8, 12])
def test_price_per_delivery_ignores_delivery_count(app, session, delivery_count):
    """ПІДТВЕРДЖЕНО ВЛАСНИКОМ: ціна за букет фіксована, ÷ 4 незалежно від N.

    Тобто підписка на 6 доставок коштує клієнту 6 × (цикл ÷ 4), а не цикл.
    Якщо колись захочуть «цикл ÷ N» — це зміна правила, не баг.
    """
    _seed_preset(session)
    client = _client(session, f'price_count_{delivery_count}')
    sub = create_subscription(client, _sub_form(delivery_count=str(delivery_count)))

    orders = Order.query.filter_by(subscription_id=sub.id).all()

    assert len(orders) == delivery_count
    assert all(o.charged_amount == CYCLE_PRICE // 4 for o in orders)
    # Сумарна вартість зростає з кількістю доставок
    assert sum(o.charged_amount for o in orders) == delivery_count * (CYCLE_PRICE // 4)


def test_one_time_order_uses_the_full_one_time_price(app, session):
    _seed_preset(session)
    client = _client(session, 'price_one_time')

    assert get_order_price(_order(session, client)) == ONE_TIME_PRICE


def test_order_discount_wins_over_client_discount(app, session):
    _seed_preset(session)
    client = _client(session, 'price_disc', personal_discount='10')

    assert get_order_price(_order(session, client, discount=25)) == int(ONE_TIME_PRICE * 0.75)


def test_client_discount_applies_when_order_has_none(app, session):
    _seed_preset(session)
    client = _client(session, 'price_client_disc', personal_discount='10')

    assert get_order_price(_order(session, client)) == int(ONE_TIME_PRICE * 0.9)


def test_custom_size_uses_custom_amount_and_skips_the_price_table(app, session):
    _seed_preset(session)
    client = _client(session, 'price_custom')

    order = _order(session, client, size='Власний', custom_amount=777)

    assert get_order_price(order) == 777


def test_price_is_none_without_an_active_preset(app, session):
    size = Settings(type='size', value='M')
    session.add(size)
    session.commit()
    client = _client(session, 'price_no_preset')

    assert get_order_price(_order(session, client)) is None


def test_price_is_none_for_a_size_missing_from_the_directory(app, session):
    _seed_preset(session)
    client = _client(session, 'price_unknown_size')

    assert get_order_price(_order(session, client, size='XXXL')) is None


# ── Лояльність: 0 → 5 → 10, і 10 — стеля ──────────────────────────────────────

def test_loyalty_discount_escalates_then_caps_at_ten_percent(app, session):
    """ПІДТВЕРДЖЕНО ВЛАСНИКОМ: 10% — стеля, скільки б продовжень не робили."""
    _seed_preset(session)
    client = _client(session, 'loyalty_cap')
    sub = create_subscription(client, _sub_form())

    seen = []
    for _ in range(6):
        sub = extend_subscription(sub)
        seen.append(sub.discount)

    assert seen == [5, 10, 10, 10, 10, 10]
    assert client.discount == 10


def test_manual_discount_above_the_cap_is_never_lowered(app, session):
    _seed_preset(session)
    client = _client(session, 'loyalty_manual', personal_discount='20')
    sub = create_subscription(client, _sub_form())

    sub = extend_subscription(sub)

    assert sub.discount == 20


# ── Мінімальний проміжок при переносі ─────────────────────────────────────────

def test_min_gap_constants_are_four_and_nine(app):
    """ПІДТВЕРДЖЕНО ВЛАСНИКОМ: букет має відстояти 4 дні (Weekly) / 9 (Bi-weekly)."""
    assert (WEEKLY_MIN_GAP_DAYS, BIWEEKLY_MIN_GAP_DAYS) == (4, 9)


def test_weekly_reschedule_skips_a_slot_that_is_too_close(app):
    # Понеділок 2026-06-01, бажаний день — ЧТ (через 3 дні < 4) → стрибок на тиждень
    monday = datetime.date(2026, 6, 1)

    result = _get_first_valid_date(monday, 'Weekly', 'ЧТ')

    assert (result - monday).days == 10
    assert result.weekday() == 3


def test_weekly_reschedule_keeps_a_slot_that_is_far_enough(app):
    # Понеділок → ПТ це 4 дні; поріг «<= 4» теж стрибає, а 5 днів (СБ) лишається
    monday = datetime.date(2026, 6, 1)

    result = _get_first_valid_date(monday, 'Weekly', 'СБ')

    assert (result - monday).days == 5


# ── Фінансовий тиждень: субота → пʼятниця ─────────────────────────────────────

def test_financial_week_runs_saturday_to_friday(app):
    """ПІДТВЕРДЖЕНО ВЛАСНИКОМ: тиждень магазину починається в суботу."""
    start, end = get_financial_week_dates()

    assert start.weekday() == 5, 'початок має бути суботою'
    assert end.weekday() == 4, 'кінець має бути пʼятницею'
    assert (end - start).days == 6


def test_financial_week_offset_shifts_by_whole_weeks(app):
    this_start, _ = get_financial_week_dates()
    prev_start, prev_end = get_financial_week_dates(-1)
    next_start, _ = get_financial_week_dates(1)

    assert (this_start - prev_start).days == 7
    assert (next_start - this_start).days == 7
    assert (this_start - prev_end).days == 1, 'тижні мають стикуватись без розриву'


# ── Масовий перерахунок історичних списань ────────────────────────────────────

def _delivered(session, client, when, charged_amount=ONE_TIME_PRICE):
    order = _order(session, client)
    order.charged_amount = charged_amount
    order.delivery_date = when
    d = Delivery(
        order_id=order.id, client_id=client.id, delivery_date=when,
        status='Доставлено', size='M', phone='+380991234567', delivery_method='courier',
    )
    session.add(d)
    session.commit()
    return d


def test_reconcile_dry_run_changes_nothing(app, session):
    _seed_preset(session)
    client = _client(session, 'recon_dry')
    _delivered(session, client, datetime.date(2026, 6, 1))

    summary = reconcile_historical_charges(dry_run=True)

    assert summary['to_process'] == 1
    assert summary['total_amount'] == ONE_TIME_PRICE
    assert Transaction.query.count() == 0
    assert client.credits in (None, 0)


def test_reconcile_creates_missing_charges_once(app, session):
    _seed_preset(session)
    client = _client(session, 'recon_apply')
    _delivered(session, client, datetime.date(2026, 6, 1))
    _delivered(session, client, datetime.date(2026, 6, 8))

    reconcile_historical_charges(dry_run=False)
    first_pass = Transaction.query.count()
    reconcile_historical_charges(dry_run=False)

    assert first_pass == 2
    assert Transaction.query.count() == 2, 'повторний прогін не має дублювати списання'
    assert client.credits == -2 * ONE_TIME_PRICE


def test_reconcile_skips_deliveries_that_are_not_delivered(app, session):
    _seed_preset(session)
    client = _client(session, 'recon_pending')
    d = _delivered(session, client, datetime.date(2026, 6, 1))
    d.status = 'Очікує'
    session.commit()

    summary = reconcile_historical_charges(dry_run=True)

    assert summary['to_process'] == 0
