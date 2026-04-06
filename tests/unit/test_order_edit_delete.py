"""
Tests for update_order / delete_order with Delivery synchronization.

Covers:
- update_order: basic field updates on Order
- update_order: syncs address fields to active Delivery records
- update_order: is_pickup=True clears street on Delivery
- update_order: does NOT sync to 'Доставлено' deliveries
- update_order: does NOT sync to 'Скасовано' deliveries
- update_order: new delivery_date applied only to first active delivery
- update_order: changes client when instagram differs
- update_order: replaces additional phones
- update_order: raises ValueError for unknown client instagram
- delete_order: removes Order, all Deliveries, RecipientPhones, RouteDeliveries
"""
import datetime
import pytest
from app.models import Client, Order, Delivery
from app.models.recipient_phone import RecipientPhone
from app.models.delivery_route import DeliveryRoute, RouteDelivery
from app.services.order_service import update_order, delete_order


class FakeForm(dict):
    def getlist(self, key):
        val = self.get(key, [])
        return val if isinstance(val, list) else [val]


def _make_client(session, instagram='edit_client'):
    c = Client(instagram=instagram)
    session.add(c)
    session.commit()
    return c


def _make_order_with_delivery(session, client, delivery_date=None, delivery_status='Очікує'):
    today = delivery_date or datetime.date.today()
    order = Order(
        client_id=client.id,
        recipient_name='Тест',
        recipient_phone='+380991234567',
        city='Київ',
        street='Хрещатик 1',
        size='M',
        delivery_date=today,
        for_whom='Дружина',
        delivery_method='courier',
    )
    session.add(order)
    session.flush()

    delivery = Delivery(
        order_id=order.id,
        client_id=client.id,
        delivery_date=today,
        status=delivery_status,
        size='M',
        phone='+380991234567',
        delivery_method='courier',
        street='Хрещатик 1',
    )
    session.add(delivery)
    session.commit()
    return order, delivery


def _base_edit_form(**overrides):
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = FakeForm({
        'client_instagram': 'edit_client',
        'recipient_name': 'Нове Імʼя',
        'recipient_phone': '+380671112233',
        'first_delivery_date': tomorrow,
        'city': 'Львів',
        'street': 'вул. Нова 10',
        'size': 'L',
        'for_whom': 'Мама',
        'delivery_method': 'courier',
        'comment': 'Новий коментар',
        'preferences': 'Нові переваги',
        'time_from': '10:00',
        'time_to': '14:00',
        'additional_phones': [],
    })
    form.update(overrides)
    return form


# ── update_order: basic field updates ────────────────────────────────────────

def test_update_order_updates_recipient_fields(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client)

    form = _base_edit_form()
    update_order(order, form)

    assert order.recipient_name == 'Нове Імʼя'
    assert order.recipient_phone == '+380671112233'
    assert order.city == 'Львів'
    assert order.size == 'L'


def test_update_order_updates_delivery_date(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client)

    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    form = _base_edit_form(first_delivery_date=tomorrow.strftime('%Y-%m-%d'))
    update_order(order, form)

    assert order.delivery_date == tomorrow


# ── update_order: sync to active Delivery ────────────────────────────────────

def test_update_order_syncs_address_to_active_delivery(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client)

    form = _base_edit_form(street='вул. Нова 10', city='Львів')
    update_order(order, form)

    session.refresh(delivery)
    assert delivery.street == 'вул. Нова 10'
    assert delivery.comment == 'Новий коментар'
    assert delivery.preferences == 'Нові переваги'


def test_update_order_syncs_phone_to_active_delivery(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client)

    form = _base_edit_form(recipient_phone='+380671112233')
    update_order(order, form)

    session.refresh(delivery)
    assert delivery.phone == '+380671112233'


# ── update_order: is_pickup clears street on Delivery ────────────────────────

def test_update_order_is_pickup_clears_delivery_street(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client)

    form = _base_edit_form(is_pickup='on')
    update_order(order, form)

    session.refresh(delivery)
    assert delivery.street is None
    assert delivery.is_pickup is True


def test_update_order_is_pickup_clears_building_floor_entrance(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client)

    form = _base_edit_form(is_pickup='on')
    update_order(order, form)

    session.refresh(delivery)
    assert delivery.building_number is None
    assert delivery.floor is None
    assert delivery.entrance is None


# ── update_order: does NOT sync to delivered/cancelled ───────────────────────

def test_update_order_does_not_sync_to_delivered_delivery(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client, delivery_status='Доставлено')

    form = _base_edit_form(street='вул. Нова 10')
    update_order(order, form)

    session.refresh(delivery)
    assert delivery.street == 'Хрещатик 1'
    assert delivery.comment is None


def test_update_order_does_not_sync_to_cancelled_delivery(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client, delivery_status='Скасовано')

    form = _base_edit_form(street='вул. Нова 10')
    update_order(order, form)

    session.refresh(delivery)
    assert delivery.street == 'Хрещатик 1'


# ── update_order: delivery_date only on first active delivery ────────────────

def test_update_order_new_date_only_on_first_active_delivery(session):
    """Subscription with 2 active deliveries: only first gets new date."""
    from app.models.subscription import Subscription
    client = _make_client(session, 'sub_edit')
    sub = Subscription(
        client_id=client.id, type='Weekly', status='active',
        delivery_day='ПН', recipient_name='R', recipient_phone='+380991234567',
        city='Київ', street='Вул. 1', size='M', for_whom='Я',
    )
    session.add(sub)
    session.flush()

    today = datetime.date(2026, 4, 6)
    next_monday = today + datetime.timedelta(days=7)

    o1 = Order(client_id=client.id, subscription_id=sub.id, sequence_number=1,
               recipient_name='R', recipient_phone='+380991234567',
               city='Київ', street='Вул. 1', size='M', delivery_date=today, for_whom='Я', delivery_method='courier')
    session.add(o1)
    session.flush()

    o2 = Order(client_id=client.id, subscription_id=sub.id, sequence_number=2,
               recipient_name='R', recipient_phone='+380991234567',
               city='Київ', street='Вул. 1', size='M', delivery_date=next_monday, for_whom='Я', delivery_method='courier')
    session.add(o2)
    session.flush()

    d1 = Delivery(order_id=o1.id, client_id=client.id, delivery_date=today, status='Очікує', size='M', phone='+380991234567', delivery_method='courier', street='Вул. 1')
    d2 = Delivery(order_id=o2.id, client_id=client.id, delivery_date=next_monday, status='Очікує', size='M', phone='+380991234567', delivery_method='courier', street='Вул. 1')
    session.add_all([d1, d2])
    session.commit()

    new_date = today + datetime.timedelta(days=3)
    form = _base_edit_form(
        client_instagram='sub_edit',
        first_delivery_date=new_date.strftime('%Y-%m-%d'),
    )
    update_order(o1, form)

    session.refresh(d1)
    session.refresh(d2)
    assert d1.delivery_date == new_date
    assert d2.delivery_date == next_monday


# ── update_order: change client ──────────────────────────────────────────────

def test_update_order_changes_client(session):
    old_client = _make_client(session, 'old_client')
    new_client = _make_client(session, 'new_client')
    order, delivery = _make_order_with_delivery(session, old_client)

    form = _base_edit_form(client_instagram='new_client')
    update_order(order, form)

    assert order.client_id == new_client.id


@pytest.mark.xfail(reason='BUG: update_order does not sync delivery.client_id when client changes')
def test_update_order_changes_client_syncs_delivery_client_id(session):
    """
    When order client changes, delivery.client_id should also be updated
    to maintain the invariant: delivery.client_id == order.client_id.
    """
    old_client = _make_client(session, 'old_client_sync')
    new_client = _make_client(session, 'new_client_sync')
    order, delivery = _make_order_with_delivery(session, old_client)

    form = _base_edit_form(client_instagram='new_client_sync')
    update_order(order, form)

    session.refresh(delivery)
    assert delivery.client_id == new_client.id


def test_update_order_unknown_client_raises_error(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client)

    form = _base_edit_form(client_instagram='nonexistent')
    with pytest.raises(ValueError, match='не знайдено'):
        update_order(order, form)


# ── update_order: replaces additional phones ─────────────────────────────────

def test_update_order_replaces_additional_phones(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client)

    session.add(RecipientPhone(order_id=order.id, phone='+380501111111', position=1))
    session.commit()

    form = _base_edit_form(additional_phones=['+380672222222', '+380933333333'])
    update_order(order, form)

    phones = RecipientPhone.query.filter_by(order_id=order.id).order_by(RecipientPhone.position).all()
    assert len(phones) == 2
    assert phones[0].phone == '+380672222222'
    assert phones[1].phone == '+380933333333'


# ── delete_order ─────────────────────────────────────────────────────────────

def test_delete_order_removes_order_and_deliveries(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client)

    order_id = order.id
    delivery_id = delivery.id

    delete_order(order)

    assert Order.query.get(order_id) is None
    assert Delivery.query.get(delivery_id) is None


def test_delete_order_removes_recipient_phones(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client)

    session.add(RecipientPhone(order_id=order.id, phone='+380501111111', position=1))
    session.commit()

    delete_order(order)

    phones = RecipientPhone.query.filter_by(order_id=order.id).all()
    assert len(phones) == 0


def test_delete_order_removes_route_deliveries(session):
    client = _make_client(session)
    order, delivery = _make_order_with_delivery(session, client)

    route = DeliveryRoute(route_date=datetime.date.today(), status='draft')
    session.add(route)
    session.flush()

    stop = RouteDelivery(route_id=route.id, delivery_id=delivery.id, stop_order=1)
    session.add(stop)
    session.commit()

    delete_order(order)

    stops = RouteDelivery.query.filter_by(delivery_id=delivery.id).all()
    assert len(stops) == 0
