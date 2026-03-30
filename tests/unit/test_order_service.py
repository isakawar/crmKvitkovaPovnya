"""
Tests for app/services/order_service.py

Covers:
- get_or_create_client: unknown instagram → (None, error)
- create_order_and_deliveries:
    * creates exactly 1 Order + 1 Delivery
    * is_pickup=True → delivery.street is None
    * custom_amount string '500' is stored as int 500
- get_orders: filter by delivery_type='One-time'

BUG stubs (xfail):
- BUG-03: past delivery_date not rejected
- BUG-04: time_from > time_to not rejected
"""
import datetime
import pytest
from app.models import Client, Order, Delivery
from app.services.order_service import (
    get_or_create_client,
    create_order_and_deliveries,
    get_orders,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

class FakeForm(dict):
    """Minimal dict-like object that also has .getlist() for multi-value fields."""

    def getlist(self, key):
        val = self.get(key, [])
        return val if isinstance(val, list) else [val]


def _base_form(**overrides):
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = FakeForm({
        'recipient_name': 'Тест Отримувач',
        'recipient_phone': '+380991234567',
        'first_delivery_date': tomorrow,
        'city': 'Київ',
        'street': 'Хрещатик 1',
        'size': 'M',
        'for_whom': 'Дружина',
        'delivery_method': 'courier',
        'additional_phones': [],
    })
    form.update(overrides)
    return form


def _make_client(session, instagram='order_client'):
    c = Client(instagram=instagram)
    session.add(c)
    session.commit()
    return c


# ── get_or_create_client ──────────────────────────────────────────────────────

def test_get_or_create_client_unknown_instagram_returns_none(session):
    client, err = get_or_create_client('nonexistent_user')
    assert client is None
    assert err is not None


def test_get_or_create_client_known_instagram_returns_client(session):
    _make_client(session, instagram='known_user')
    client, err = get_or_create_client('known_user')
    assert err is None
    assert client is not None
    assert client.instagram == 'known_user'


# ── create_order_and_deliveries ───────────────────────────────────────────────

def test_create_order_creates_exactly_one_delivery(session):
    client = _make_client(session, 'onetime_client')
    form = _base_form()

    create_order_and_deliveries(client, form)

    orders = Order.query.filter_by(client_id=client.id).all()
    deliveries = Delivery.query.filter_by(client_id=client.id).all()
    assert len(orders) == 1
    assert len(deliveries) == 1


def test_create_order_delivery_date_matches_form(session):
    client = _make_client(session, 'date_client')
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    form = _base_form(first_delivery_date=tomorrow.strftime('%Y-%m-%d'))

    create_order_and_deliveries(client, form)

    delivery = Delivery.query.filter_by(client_id=client.id).first()
    assert delivery.delivery_date == tomorrow


def test_create_order_is_pickup_delivery_has_no_street(session):
    """When is_pickup=on, street must not be copied to Delivery."""
    client = _make_client(session, 'pickup_client')
    form = _base_form(is_pickup='on')

    create_order_and_deliveries(client, form)

    delivery = Delivery.query.filter_by(client_id=client.id).first()
    assert delivery.street is None


def test_create_order_custom_amount_stored_as_int(session):
    client = _make_client(session, 'custom_amount_client')
    form = _base_form(size='Власний', custom_amount='500')

    create_order_and_deliveries(client, form)

    order = Order.query.filter_by(client_id=client.id).first()
    assert order.custom_amount == 500
    assert isinstance(order.custom_amount, int)


# ── get_orders: filtering ─────────────────────────────────────────────────────

def test_get_orders_returns_one_time_orders_only(session):
    """delivery_type='One-time' must return only orders with no subscription_id."""
    c1 = _make_client(session, 'filter_client_1')
    c2 = _make_client(session, 'filter_client_2')

    # One-time order (no subscription)
    form1 = _base_form()
    create_order_and_deliveries(c1, form1)

    # Subscription order (with subscription_id set manually)
    from app.models.subscription import Subscription
    sub = Subscription(
        client_id=c2.id,
        type='Weekly',
        status='active',
        delivery_day='ПН',
        recipient_name='R',
        recipient_phone='+380991234568',
        city='Київ',
        street='Вул. 1',
        size='M',
        for_whom='Дружина',
    )
    session.add(sub)
    session.flush()

    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    sub_order = Order(
        client_id=c2.id,
        subscription_id=sub.id,
        sequence_number=1,
        recipient_name='R',
        recipient_phone='+380991234568',
        city='Київ',
        street='Вул. 1',
        size='M',
        delivery_date=tomorrow,
        for_whom='Дружина',
        delivery_method='courier',
    )
    session.add(sub_order)
    session.commit()

    results = get_orders(delivery_type='One-time')
    ids = [o.id for o in results]
    one_time = Order.query.filter_by(client_id=c1.id).first()
    sub_o = Order.query.filter_by(client_id=c2.id).first()

    assert one_time.id in ids
    assert sub_o.id not in ids


# ── BUG stubs (xfail) ─────────────────────────────────────────────────────────

@pytest.mark.xfail(reason='BUG-03: delivery_date in the past is not validated')
def test_create_order_rejects_past_delivery_date(session):
    """
    BUG-03: order_service.create_order_and_deliveries accepts past dates.
    This test documents the expected behaviour after the bug is fixed.
    """
    client = _make_client(session, 'past_date_client')
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = _base_form(first_delivery_date=yesterday)

    # After fix: should raise ValueError or return an error
    with pytest.raises((ValueError, Exception)):
        create_order_and_deliveries(client, form)


@pytest.mark.xfail(reason='BUG-04: time_from > time_to is not validated')
def test_create_order_rejects_invalid_time_range(session):
    """
    BUG-04: no check that time_from < time_to.
    This test documents the expected behaviour after the bug is fixed.
    """
    client = _make_client(session, 'time_range_client')
    form = _base_form(time_from='18:00', time_to='10:00')  # invalid range

    with pytest.raises((ValueError, Exception)):
        create_order_and_deliveries(client, form)
