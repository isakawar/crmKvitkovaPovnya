"""Дедуплікація клієнтів, генерація кодів і синхронізація order.delivery_date."""
import datetime

from app.extensions import db
from app.models import Client, Order, Delivery
from app.models.certificate import Certificate, generate_certificate_code
from app.models.promo_code import PromoCode, generate_promo_code
from app.models.subscription import Subscription
from app.services.csv_import_service import find_existing_client
from app.services.client_service import find_client_by_handle
from app.services.order_service import sync_order_delivery_date
from app.services.subscription_service import (
    build_resume_plan,
    apply_resume_plan,
    schedule_single_delivery,
)


# ── дедуплікація клієнтів ─────────────────────────────────────────────────────

def test_import_matches_client_case_insensitively(app, session):
    """Імпорт заводив дубль там, де форма створення показала б наявного клієнта."""
    session.add(Client(instagram='Ivanna'))
    session.commit()

    assert find_existing_client(instagram='ivanna') is not None
    assert find_existing_client(instagram='IVANNA') is not None


def test_import_matches_client_ignoring_at_prefix(app, session):
    session.add(Client(telegram='@some_handle'))
    session.commit()

    assert find_existing_client(telegram='some_handle') is not None
    assert find_existing_client(telegram='@SOME_HANDLE') is not None


def test_handle_lookup_ignores_blank(app, session):
    session.add(Client(instagram='someone'))
    session.commit()

    assert find_client_by_handle(Client.instagram, '') is None
    assert find_client_by_handle(Client.instagram, '@') is None
    assert find_client_by_handle(Client.instagram, None) is None


# ── генерація кодів ───────────────────────────────────────────────────────────

def _cert(session, code, **over):
    c = Certificate(
        code=code, type='amount', value_amount=100,
        expires_at=datetime.date.today() + datetime.timedelta(days=365),
        status='active', **over,
    )
    session.add(c)
    session.commit()
    return c


def test_certificate_code_is_derived_from_codes_not_ids(app, session):
    """Сортування за id давало неправильний «останній» код і колізію по UNIQUE."""
    _cert(session, 'Р0001')
    _cert(session, 'Р0005')
    # Рядок із меншим номером створено ПІЗНІШЕ — тобто має найбільший id.
    _cert(session, 'Р0002')

    assert generate_certificate_code('amount') == 'Р0003'


def test_certificate_code_fills_first_free_slot(app, session):
    _cert(session, 'Р0001')
    _cert(session, 'Р0003')

    assert generate_certificate_code('amount') == 'Р0002'


def test_certificate_code_prefix_per_type(app, session):
    _cert(session, 'Р0001')
    assert generate_certificate_code('subscription') == 'П0001'


def test_promo_code_is_derived_from_codes_not_ids(app, session):
    for code in ('PROMO0001', 'PROMO0004', 'PROMO0002'):
        session.add(PromoCode(code=code, name=code, discount_percent=5))
    session.commit()

    assert generate_promo_code() == 'PROMO0003'


# ── order.delivery_date тримається синхронним ─────────────────────────────────

def _sub_with_orders(session, client, dates):
    sub = Subscription(
        client_id=client.id, type='Weekly', status='active', delivery_day='ПН',
        recipient_name='Отримувач', recipient_phone='+380991234567',
        city='Київ', street='Хрещатик 1', size='M', for_whom='Дружина',
    )
    session.add(sub)
    session.flush()
    orders = []
    for i, d in enumerate(dates, start=1):
        o = Order(
            client_id=client.id, subscription_id=sub.id, sequence_number=i,
            recipient_name='Отримувач', recipient_phone='+380991234567',
            city='Київ', street='Хрещатик 1', is_pickup=False,
            delivery_method='courier', size='M', delivery_date=d, for_whom='Дружина',
        )
        session.add(o)
        session.flush()
        session.add(Delivery(
            order_id=o.id, client_id=client.id, delivery_date=d,
            status='Очікує', size='M', phone='+380991234567', delivery_method='courier',
        ))
        orders.append(o)
    session.commit()
    return sub, orders


def test_sync_uses_earliest_pending_delivery(app, session):
    client = Client(instagram='sync_1')
    session.add(client)
    session.commit()
    today = datetime.date.today()
    _, orders = _sub_with_orders(session, client, [today])
    order = orders[0]

    order.deliveries[0].delivery_date = today + datetime.timedelta(days=10)
    sync_order_delivery_date(order)

    assert order.delivery_date == today + datetime.timedelta(days=10)


def test_sync_falls_back_to_last_completed_when_nothing_pending(app, session):
    client = Client(instagram='sync_2')
    session.add(client)
    session.commit()
    today = datetime.date.today()
    _, orders = _sub_with_orders(session, client, [today])
    order = orders[0]
    order.deliveries[0].status = 'Доставлено'
    session.commit()

    sync_order_delivery_date(order)

    assert order.delivery_date == today


def test_resume_plan_keeps_order_delivery_date_in_step(app, session):
    client = Client(instagram='sync_3')
    session.add(client)
    session.commit()
    today = datetime.date.today()
    sub, orders = _sub_with_orders(
        session, client, [today, today + datetime.timedelta(days=7)]
    )
    sub.is_stopped = True
    session.commit()

    new_first = today + datetime.timedelta(days=30)
    apply_resume_plan(sub, build_resume_plan(sub, new_first))
    session.commit()

    for order in orders:
        pending = [d.delivery_date for d in order.deliveries]
        assert order.delivery_date == min(pending)


def test_schedule_single_delivery_updates_order_date(app, session):
    client = Client(instagram='sync_4')
    session.add(client)
    session.commit()
    today = datetime.date.today()
    sub, orders = _sub_with_orders(session, client, [today])
    delivery = orders[0].deliveries[0]

    new_date = today + datetime.timedelta(days=21)
    schedule_single_delivery(sub, delivery.id, new_date)
    session.commit()

    assert orders[0].delivery_date == new_date
