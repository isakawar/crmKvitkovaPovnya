"""
Tests for app/services/delivery_service.py

Covers:
- get_financial_week_dates (current week, offset +1)
- group_deliveries_by_date
- set_delivery_status:
    * Розподілено → Доставлено increments courier.deliveries_count
    * Очікує → Доставлено does NOT increment (documented behaviour, BUG-suspicious#4)
    * delivered_at is set only on first Доставлено transition
- assign_deliveries: resets only submitted IDs, then assigns
"""
import datetime
import itertools
import pytest
from app.models import Client, Courier, Order, Delivery
from app.services.delivery_service import (
    get_financial_week_dates,
    group_deliveries_by_date,
    set_delivery_status,
    assign_deliveries,
)


# ── get_financial_week_dates ──────────────────────────────────────────────────

def test_financial_week_spans_saturday_to_friday():
    start, end = get_financial_week_dates(0)
    assert start.weekday() == 5, 'Start should be Saturday (weekday=5)'
    assert end.weekday() == 4, 'End should be Friday (weekday=4)'
    assert (end - start).days == 6


def test_financial_week_contains_today():
    start, end = get_financial_week_dates(0)
    today = datetime.date.today()
    assert start <= today <= end


def test_financial_week_offset_plus1_is_next_week():
    start0, end0 = get_financial_week_dates(0)
    start1, end1 = get_financial_week_dates(1)
    assert start1 == start0 + datetime.timedelta(days=7)
    assert end1 == end0 + datetime.timedelta(days=7)


# ── group_deliveries_by_date ──────────────────────────────────────────────────

def test_group_deliveries_by_date(session):
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    client = Client(instagram='grp_client')
    session.add(client)
    session.flush()

    order = Order(
        client_id=client.id,
        recipient_name='R',
        recipient_phone='+380991234567',
        city='Київ',
        street='Вул. 1',
        size='M',
        delivery_date=today,
        for_whom='Я',
        delivery_method='courier',
    )
    session.add(order)
    session.flush()

    d1 = Delivery(order_id=order.id, client_id=client.id, delivery_date=today,
                  status='Очікує', size='M', phone='+380991234567', delivery_method='courier')
    d2 = Delivery(order_id=order.id, client_id=client.id, delivery_date=today,
                  status='Очікує', size='M', phone='+380991234567', delivery_method='courier')
    d3 = Delivery(order_id=order.id, client_id=client.id, delivery_date=tomorrow,
                  status='Очікує', size='M', phone='+380991234567', delivery_method='courier')
    session.add_all([d1, d2, d3])
    session.commit()

    grouped = group_deliveries_by_date([d1, d2, d3])

    assert today in grouped
    assert tomorrow in grouped
    assert len(grouped[today]) == 2
    assert len(grouped[tomorrow]) == 1


# ── set_delivery_status ───────────────────────────────────────────────────────

_counter = itertools.count(1)


def _make_delivery_with_courier(session, initial_status='Очікує'):
    """Helper: create Client, Courier, Order, Delivery in the given session."""
    n = next(_counter)
    client = Client(instagram=f'del_client_{n}')
    courier = Courier(name='Тест Кур', phone=f'+38099{n:07d}',
                      deliveries_count=0)
    session.add_all([client, courier])
    session.flush()

    order = Order(
        client_id=client.id,
        recipient_name='R',
        recipient_phone='+380991234567',
        city='Київ',
        street='Вул. 1',
        size='M',
        delivery_date=datetime.date.today(),
        for_whom='Я',
        delivery_method='courier',
    )
    session.add(order)
    session.flush()

    delivery = Delivery(
        order_id=order.id,
        client_id=client.id,
        delivery_date=datetime.date.today(),
        status=initial_status,
        courier_id=courier.id,
        size='M',
        phone='+380991234567',
        delivery_method='courier',
    )
    session.add(delivery)
    session.commit()
    return delivery, courier


def test_set_delivery_status_rozpodileno_to_dostavleno_increments_count(session):
    delivery, courier = _make_delivery_with_courier(session, 'Розподілено')
    initial_count = courier.deliveries_count

    set_delivery_status(delivery, 'Доставлено')

    assert courier.deliveries_count == initial_count + 1


def test_set_delivery_status_ochikuye_to_dostavleno_does_not_increment(session):
    """
    Documented behaviour (SUSPICIOUS #4 / BUG-like):
    deliveries_count is incremented ONLY on the Розподілено→Доставлено transition.
    Direct Очікує→Доставлено does NOT increment the counter.
    This test documents the current behaviour — if the bug is ever fixed,
    this test should be updated to expect count + 1.
    """
    delivery, courier = _make_delivery_with_courier(session, 'Очікує')
    initial_count = courier.deliveries_count

    set_delivery_status(delivery, 'Доставлено')

    # Current (known) behaviour: count is NOT incremented
    assert courier.deliveries_count == initial_count


def test_set_delivery_status_delivered_at_set_on_first_dostavleno(session):
    delivery, _ = _make_delivery_with_courier(session, 'Розподілено')
    assert delivery.delivered_at is None

    set_delivery_status(delivery, 'Доставлено')
    first_delivered_at = delivery.delivered_at
    assert first_delivered_at is not None


def test_set_delivery_status_delivered_at_not_overwritten(session):
    """delivered_at should not change if status was already Доставлено."""
    delivery, _ = _make_delivery_with_courier(session, 'Розподілено')

    set_delivery_status(delivery, 'Доставлено')
    first_ts = delivery.delivered_at

    # Simulate a second transition (e.g. revert + re-deliver)
    delivery.status = 'Розподілено'
    set_delivery_status(delivery, 'Доставлено')

    assert delivery.delivered_at == first_ts


# ── assign_deliveries ─────────────────────────────────────────────────────────

def test_assign_deliveries_assigns_courier_and_sets_status(session):
    delivery, courier = _make_delivery_with_courier(session, 'Очікує')

    assign_deliveries({str(courier.id): [delivery.id]})

    session.refresh(delivery)
    assert delivery.courier_id == courier.id
    assert delivery.status == 'Розподілено'


def test_assign_deliveries_unassigned_key_resets_to_ochikuye(session):
    delivery, courier = _make_delivery_with_courier(session, 'Розподілено')
    delivery.courier_id = courier.id
    session.commit()

    # Submit all IDs under 'unassigned' — they should be reset
    assign_deliveries({'unassigned': [delivery.id]})

    session.refresh(delivery)
    assert delivery.courier_id is None
    assert delivery.status == 'Очікує'


def test_assign_deliveries_only_touches_submitted_ids(session):
    """Deliveries NOT in the submitted set must be left untouched."""
    d1, courier = _make_delivery_with_courier(session, 'Розподілено')
    d2, _ = _make_delivery_with_courier(session, 'Розподілено')

    # Only reassign d1; d2 should remain Розподілено
    assign_deliveries({str(courier.id): [d1.id]})

    session.refresh(d2)
    assert d2.status == 'Розподілено'
