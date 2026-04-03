"""
Tests for calculate_reschedule_plan and apply_reschedule_plan.

Covers:
- calculate_reschedule_plan: returns None for Monthly subscriptions
- calculate_reschedule_plan: returns None when date change <= 2 days
- calculate_reschedule_plan: returns None when no pending next orders
- calculate_reschedule_plan: returns None when gap > threshold
- calculate_reschedule_plan: returns valid plan for Weekly with close next delivery
- calculate_reschedule_plan: returns valid plan for Bi-weekly with close next delivery
- calculate_reschedule_plan: plan contains correct suggested dates
- apply_reschedule_plan: updates delivery dates of subsequent pending orders
- apply_reschedule_plan: does NOT touch delivered/cancelled deliveries
- apply_reschedule_plan: resets Розподілено deliveries to Очікує and removes RouteDelivery
- apply_reschedule_plan: returns count of updated deliveries
- _get_first_valid_date: Weekly respects min gap (shared logic)
- _get_first_valid_date: Bi-weekly respects min gap (shared logic)
"""
import datetime
import pytest
from app.models import Client, Order, Delivery
from app.models.subscription import Subscription
from app.models.delivery_route import DeliveryRoute, RouteDelivery
from app.services.subscription_service import (
    calculate_reschedule_plan,
    apply_reschedule_plan,
    _get_first_valid_date,
    WEEKLY_MIN_GAP_DAYS,
    BIWEEKLY_MIN_GAP_DAYS,
)


def _make_subscription_with_orders(session, sub_type='Weekly', delivery_day='ПН', start_date=None, num_orders=4):
    """Create a subscription with N orders and deliveries."""
    client = Client(instagram=f'resched_{sub_type}')
    session.add(client)
    session.flush()

    sub = Subscription(
        client_id=client.id,
        type=sub_type,
        status='active',
        delivery_day=delivery_day,
        recipient_name='R',
        recipient_phone='+380991234567',
        city='Київ',
        street='Вул. 1',
        size='M',
        for_whom='Я',
    )
    session.add(sub)
    session.flush()

    if start_date is None:
        start_date = datetime.date(2026, 3, 30)  # Monday

    interval = 7 if sub_type == 'Weekly' else 14
    orders = []
    deliveries = []
    for i in range(num_orders):
        d_date = start_date + datetime.timedelta(days=interval * i)
        order = Order(
            client_id=client.id,
            subscription_id=sub.id,
            sequence_number=i + 1,
            recipient_name='R',
            recipient_phone='+380991234567',
            city='Київ',
            street='Вул. 1',
            size='M',
            delivery_date=d_date,
            for_whom='Я',
            delivery_method='courier',
        )
        session.add(order)
        session.flush()

        delivery = Delivery(
            order_id=order.id,
            client_id=client.id,
            delivery_date=d_date,
            status='Очікує',
            size='M',
            phone='+380991234567',
            delivery_method='courier',
            street='Вул. 1',
        )
        session.add(delivery)
        orders.append(order)
        deliveries.append(delivery)

    session.commit()
    return sub, orders, deliveries


# ── calculate_reschedule_plan: rejection cases ───────────────────────────────

def test_reschedule_plan_returns_none_for_monthly(session):
    sub, orders, deliveries = _make_subscription_with_orders(session, sub_type='Monthly')
    delivery = deliveries[0]
    old_date = delivery.delivery_date
    new_date = old_date + datetime.timedelta(days=5)

    result = calculate_reschedule_plan(delivery, old_date, new_date)
    assert result is None


def test_reschedule_plan_returns_none_when_change_small(session):
    sub, orders, deliveries = _make_subscription_with_orders(session)
    delivery = deliveries[0]
    old_date = delivery.delivery_date
    new_date = old_date + datetime.timedelta(days=2)

    result = calculate_reschedule_plan(delivery, old_date, new_date)
    assert result is None


def test_reschedule_plan_returns_none_when_no_pending_next(session):
    """All subsequent orders are already delivered."""
    sub, orders, deliveries = _make_subscription_with_orders(session)
    for d in deliveries[1:]:
        d.status = 'Доставлено'
    session.commit()

    delivery = deliveries[0]
    old_date = delivery.delivery_date
    new_date = old_date + datetime.timedelta(days=5)

    result = calculate_reschedule_plan(delivery, old_date, new_date)
    assert result is None


def test_reschedule_plan_returns_none_when_gap_too_large(session):
    """
    When the gap from new_date to the next pending delivery exceeds the threshold,
    no reschedule plan is returned.

    Uses a date change > 2 days (to pass the early return) but with a large
    enough gap to the next delivery that rescheduling is unnecessary.
    """
    sub, orders, deliveries = _make_subscription_with_orders(session)
    delivery = deliveries[0]
    old_date = datetime.date(2026, 3, 30)  # Monday
    new_date = datetime.date(2026, 3, 27)  # Friday, 3 days earlier (> 2 day threshold)

    delivery.delivery_date = new_date
    session.commit()

    result = calculate_reschedule_plan(delivery, old_date, new_date)
    assert result is None


def test_reschedule_plan_returns_none_for_one_time_order(session):
    """Order without subscription_id returns None."""
    client = Client(instagram='reshed_one_time')
    session.add(client)
    session.flush()

    order = Order(
        client_id=client.id,
        recipient_name='R',
        recipient_phone='+380991234567',
        city='Київ',
        street='Вул. 1',
        size='M',
        delivery_date=datetime.date(2026, 3, 30),
        for_whom='Я',
        delivery_method='courier',
    )
    session.add(order)
    session.flush()

    delivery = Delivery(
        order_id=order.id,
        client_id=client.id,
        delivery_date=datetime.date(2026, 3, 30),
        status='Очікує',
        size='M',
        phone='+380991234567',
        delivery_method='courier',
        street='Вул. 1',
    )
    session.add(delivery)
    session.commit()

    result = calculate_reschedule_plan(delivery, delivery.delivery_date, delivery.delivery_date + datetime.timedelta(days=5))
    assert result is None


# ── calculate_reschedule_plan: valid plan ─────────────────────────────────────

def _make_close_gap_weekly_subscription(session):
    """
    Create a Weekly subscription where the first delivery is moved forward
    so that the gap to the next delivery becomes <= 4 days (threshold).

    Monday (Mar 30) -> moved to Thursday (Apr 2).
    Next delivery is Monday (Apr 6). Gap = 4 days = threshold.
    This should trigger a reschedule plan.
    """
    client = Client(instagram='reshed_close')
    session.add(client)
    session.flush()

    sub = Subscription(
        client_id=client.id, type='Weekly', status='active',
        delivery_day='ПН', recipient_name='R', recipient_phone='+380991234567',
        city='Київ', street='Вул. 1', size='M', for_whom='Я',
    )
    session.add(sub)
    session.flush()

    mon1 = datetime.date(2026, 3, 30)
    mon2 = datetime.date(2026, 4, 6)
    mon3 = datetime.date(2026, 4, 13)

    o1 = Order(client_id=client.id, subscription_id=sub.id, sequence_number=1,
               recipient_name='R', recipient_phone='+380991234567',
               city='Київ', street='Вул. 1', size='M', delivery_date=mon1, for_whom='Я', delivery_method='courier')
    session.add(o1)
    session.flush()

    o2 = Order(client_id=client.id, subscription_id=sub.id, sequence_number=2,
               recipient_name='R', recipient_phone='+380991234567',
               city='Київ', street='Вул. 1', size='M', delivery_date=mon2, for_whom='Я', delivery_method='courier')
    session.add(o2)
    session.flush()

    o3 = Order(client_id=client.id, subscription_id=sub.id, sequence_number=3,
               recipient_name='R', recipient_phone='+380991234567',
               city='Київ', street='Вул. 1', size='M', delivery_date=mon3, for_whom='Я', delivery_method='courier')
    session.add(o3)
    session.flush()

    d1 = Delivery(order_id=o1.id, client_id=client.id, delivery_date=mon1, status='Очікує', size='M', phone='+380991234567', delivery_method='courier', street='Вул. 1')
    d2 = Delivery(order_id=o2.id, client_id=client.id, delivery_date=mon2, status='Очікує', size='M', phone='+380991234567', delivery_method='courier', street='Вул. 1')
    d3 = Delivery(order_id=o3.id, client_id=client.id, delivery_date=mon3, status='Очікує', size='M', phone='+380991234567', delivery_method='courier', street='Вул. 1')
    session.add_all([d1, d2, d3])
    session.commit()

    return sub, [o1, o2, o3], [d1, d2, d3]


def test_reschedule_plan_returns_valid_plan_for_weekly(session):
    sub, orders, deliveries = _make_close_gap_weekly_subscription(session)
    delivery = deliveries[0]
    old_date = datetime.date(2026, 3, 30)
    new_date = datetime.date(2026, 4, 2)

    result = calculate_reschedule_plan(delivery, old_date, new_date)

    assert result is not None
    assert result['subscription_type'] == 'Weekly'
    assert result['gap_days'] == 4
    assert result['desired_weekday'] == 'ПН'
    assert result['count'] == 2
    assert len(result['deliveries']) == 2

    first_suggestion = result['deliveries'][0]
    assert first_suggestion['order_id'] == orders[1].id
    assert first_suggestion['sequence_number'] == 2
    assert first_suggestion['current_date'] == '06.04'

    second_suggestion = result['deliveries'][1]
    assert second_suggestion['order_id'] == orders[2].id
    assert second_suggestion['sequence_number'] == 3


def test_reschedule_plan_includes_changed_info(session):
    sub, orders, deliveries = _make_close_gap_weekly_subscription(session)
    delivery = deliveries[0]
    old_date = datetime.date(2026, 3, 30)
    new_date = datetime.date(2026, 4, 2)

    result = calculate_reschedule_plan(delivery, old_date, new_date)

    assert result is not None
    assert result['changed_delivery_id'] == delivery.id
    assert result['changed_from'] == '30.03'
    assert result['changed_to'] == '02.04'


def test_reschedule_plan_returns_valid_plan_for_biweekly(session):
    """
    Bi-weekly end-to-end: move first delivery forward so gap to next <= 9 days.
    Monday Mar 30 -> moved to Thursday Apr 2.
    Next delivery is Monday Apr 13 (14 days later). Gap = 11 days > 9 threshold.
    Need to move closer: move to Apr 6 (Monday). Gap = 7 days <= 9.
    """
    client = Client(instagram='reshed_biweekly')
    session.add(client)
    session.flush()

    sub = Subscription(
        client_id=client.id, type='Bi-weekly', status='active',
        delivery_day='ПН', recipient_name='R', recipient_phone='+380991234567',
        city='Київ', street='Вул. 1', size='M', for_whom='Я',
    )
    session.add(sub)
    session.flush()

    mon1 = datetime.date(2026, 3, 30)
    mon2 = datetime.date(2026, 4, 13)
    mon3 = datetime.date(2026, 4, 27)

    o1 = Order(client_id=client.id, subscription_id=sub.id, sequence_number=1,
               recipient_name='R', recipient_phone='+380991234567',
               city='Київ', street='Вул. 1', size='M', delivery_date=mon1, for_whom='Я', delivery_method='courier')
    session.add(o1)
    session.flush()

    o2 = Order(client_id=client.id, subscription_id=sub.id, sequence_number=2,
               recipient_name='R', recipient_phone='+380991234567',
               city='Київ', street='Вул. 1', size='M', delivery_date=mon2, for_whom='Я', delivery_method='courier')
    session.add(o2)
    session.flush()

    o3 = Order(client_id=client.id, subscription_id=sub.id, sequence_number=3,
               recipient_name='R', recipient_phone='+380991234567',
               city='Київ', street='Вул. 1', size='M', delivery_date=mon3, for_whom='Я', delivery_method='courier')
    session.add(o3)
    session.flush()

    d1 = Delivery(order_id=o1.id, client_id=client.id, delivery_date=mon1, status='Очікує', size='M', phone='+380991234567', delivery_method='courier', street='Вул. 1')
    d2 = Delivery(order_id=o2.id, client_id=client.id, delivery_date=mon2, status='Очікує', size='M', phone='+380991234567', delivery_method='courier', street='Вул. 1')
    d3 = Delivery(order_id=o3.id, client_id=client.id, delivery_date=mon3, status='Очікує', size='M', phone='+380991234567', delivery_method='courier', street='Вул. 1')
    session.add_all([d1, d2, d3])
    session.commit()

    delivery = d1
    old_date = datetime.date(2026, 3, 30)
    new_date = datetime.date(2026, 4, 6)

    result = calculate_reschedule_plan(delivery, old_date, new_date)

    assert result is not None
    assert result['subscription_type'] == 'Bi-weekly'
    assert result['gap_days'] == 7
    assert result['desired_weekday'] == 'ПН'
    assert result['count'] == 2
    assert len(result['deliveries']) == 2


# ── apply_reschedule_plan ────────────────────────────────────────────────────

def test_apply_reschedule_plan_updates_subsequent_delivery_dates(session):
    sub, orders, deliveries = _make_close_gap_weekly_subscription(session)

    delivery = deliveries[0]
    delivery.delivery_date = datetime.date(2026, 4, 2)
    session.commit()

    count = apply_reschedule_plan(delivery)

    session.refresh(deliveries[1])
    session.refresh(deliveries[2])

    assert count >= 1
    assert deliveries[1].delivery_date > datetime.date(2026, 4, 2)
    assert deliveries[2].delivery_date > deliveries[1].delivery_date


def test_apply_reschedule_plan_does_not_touch_delivered_deliveries(session):
    sub, orders, deliveries = _make_close_gap_weekly_subscription(session)

    deliveries[1].status = 'Доставлено'
    session.commit()

    delivery = deliveries[0]
    delivery.delivery_date = datetime.date(2026, 4, 2)
    session.commit()

    original_date = deliveries[1].delivery_date
    count = apply_reschedule_plan(delivery)

    session.refresh(deliveries[1])
    assert deliveries[1].delivery_date == original_date


def test_apply_reschedule_plan_does_not_touch_cancelled_deliveries(session):
    sub, orders, deliveries = _make_close_gap_weekly_subscription(session)

    deliveries[1].status = 'Скасовано'
    session.commit()

    delivery = deliveries[0]
    delivery.delivery_date = datetime.date(2026, 4, 2)
    session.commit()

    original_date = deliveries[1].delivery_date
    count = apply_reschedule_plan(delivery)

    session.refresh(deliveries[1])
    assert deliveries[1].delivery_date == original_date
    assert deliveries[1].status == 'Скасовано'


def test_apply_reschedule_plan_resets_rozpodileno_to_ochikuye(session):
    sub, orders, deliveries = _make_close_gap_weekly_subscription(session)

    deliveries[1].status = 'Розподілено'
    session.commit()

    delivery = deliveries[0]
    delivery.delivery_date = datetime.date(2026, 4, 2)
    session.commit()

    count = apply_reschedule_plan(delivery)

    session.refresh(deliveries[1])
    assert deliveries[1].status == 'Очікує'


def test_apply_reschedule_plan_removes_route_delivery_for_rozpodileno(session):
    sub, orders, deliveries = _make_close_gap_weekly_subscription(session)

    deliveries[1].status = 'Розподілено'
    session.commit()

    route = DeliveryRoute(route_date=datetime.date.today(), status='draft')
    session.add(route)
    session.flush()

    stop = RouteDelivery(route_id=route.id, delivery_id=deliveries[1].id, stop_order=1)
    session.add(stop)
    session.commit()

    delivery = deliveries[0]
    delivery.delivery_date = datetime.date(2026, 4, 2)
    session.commit()

    apply_reschedule_plan(delivery)

    stops = RouteDelivery.query.filter_by(delivery_id=deliveries[1].id).all()
    assert len(stops) == 0


def test_apply_reschedule_plan_returns_updated_count(session):
    sub, orders, deliveries = _make_close_gap_weekly_subscription(session)

    delivery = deliveries[0]
    delivery.delivery_date = datetime.date(2026, 4, 2)
    session.commit()

    count = apply_reschedule_plan(delivery)

    assert count == 2


# ── _get_first_valid_date (shared logic) ─────────────────────────────────────

def test_get_first_valid_date_weekly_respects_min_gap():
    thursday = datetime.date(2026, 4, 2)
    assert thursday.weekday() == 3

    result = _get_first_valid_date(thursday, 'Weekly', 'ПН')
    gap = (result - thursday).days
    assert gap > WEEKLY_MIN_GAP_DAYS
    assert result.weekday() == 0


def test_get_first_valid_date_biweekly_respects_min_gap():
    monday = datetime.date(2026, 3, 30)

    result = _get_first_valid_date(monday, 'Bi-weekly', 'ЧТ')
    gap = (result - monday).days
    assert gap > BIWEEKLY_MIN_GAP_DAYS
    assert result.weekday() == 3


def test_get_first_valid_date_weekly_when_gap_is_sufficient():
    thursday = datetime.date(2026, 4, 2)
    result = _get_first_valid_date(thursday, 'Weekly', 'ПТ')
    gap = (result - thursday).days
    assert gap > WEEKLY_MIN_GAP_DAYS
    assert result.weekday() == 4


def test_get_first_valid_date_already_on_desired_weekday():
    monday = datetime.date(2026, 3, 30)
    result = _get_first_valid_date(monday, 'Weekly', 'ПН')
    gap = (result - monday).days
    assert gap == 7
    assert result.weekday() == 0
