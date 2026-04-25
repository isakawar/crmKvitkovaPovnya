"""
Tests for subscription creation (4 deliveries generation)

Covers:
- create_subscription: creates 1 Subscription + 4 Orders + 4 Deliveries
- create_subscription: Weekly type generates correct date sequence
- create_subscription: Bi-weekly type generates correct date sequence
- create_subscription: Monthly type generates correct date sequence
- create_subscription: is_pickup=True → all deliveries have no street
- create_subscription: time_from/time_to only on first order
- create_subscription: comment only on first order
- extend_subscription: adds another 4 orders/deliveries
- extend_subscription: sets is_extended=True and followup_status='extended'
- create_subscription_from_import: delivery_number=1 → 4 deliveries
- create_subscription_from_import: delivery_number=2 → 3 deliveries
- create_subscription_from_import: delivery_number=3 → 2 deliveries
- create_subscription_from_import: delivery_number=4 → 1 delivery
- create_subscription_from_import: delivery_number=5 → renewal reminder only
- delete_subscription: removes all orders and deliveries
- create_draft_subscription: creates draft with status='draft'
"""
import datetime
import pytest
from app.models import Client, Order, Delivery
from app.models.subscription import Subscription
from app.services.subscription_service import (
    create_subscription,
    extend_subscription,
    delete_subscription,
    create_subscription_from_import,
    create_draft_subscription,
    get_draft_subscriptions,
)


class FakeForm(dict):
    def getlist(self, key):
        val = self.get(key, [])
        return val if isinstance(val, list) else [val]


def _base_subscription_form(**overrides):
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
        'delivery_type': 'Weekly',
        'delivery_day': 'ПН',
        'time_from': '09:00',
        'time_to': '12:00',
        'comment': 'Тестовий коментар',
        'preferences': '',
        'bouquet_type': '',
        'composition_type': '',
        'additional_phones': [],
    })
    form.update(overrides)
    return form


def _make_client(session, instagram='sub_client'):
    c = Client(instagram=instagram)
    session.add(c)
    session.commit()
    return c


# ── create_subscription: basic structure ─────────────────────────────────────

def test_create_subscription_creates_1_sub_4_orders_4_deliveries(session):
    client = _make_client(session, 'basic_sub')
    form = _base_subscription_form()

    sub = create_subscription(client, form)

    assert sub is not None
    assert sub.type == 'Weekly'
    assert sub.status == 'active'

    orders = Order.query.filter_by(subscription_id=sub.id).all()
    deliveries = Delivery.query.filter_by(client_id=client.id).all()
    assert len(orders) == 4
    assert len(deliveries) == 4


def test_create_subscription_orders_have_sequential_numbers(session):
    client = _make_client(session, 'seq_sub')
    form = _base_subscription_form()

    sub = create_subscription(client, form)
    orders = Order.query.filter_by(subscription_id=sub.id).order_by(Order.sequence_number).all()

    for i, order in enumerate(orders):
        assert order.sequence_number == i + 1


def test_create_subscription_all_orders_linked_to_subscription(session):
    client = _make_client(session, 'link_sub')
    form = _base_subscription_form()

    sub = create_subscription(client, form)
    orders = Order.query.filter_by(subscription_id=sub.id).all()

    for order in orders:
        assert order.subscription_id == sub.id


# ── create_subscription: date sequences by type ──────────────────────────────

def test_create_subscription_weekly_dates_are_7_days_apart(session):
    client = _make_client(session, 'weekly_sub')
    monday = datetime.date(2026, 3, 30)
    form = _base_subscription_form(
        first_delivery_date=monday.strftime('%Y-%m-%d'),
        delivery_type='Weekly',
        delivery_day='ПН',
    )

    sub = create_subscription(client, form)
    orders = Order.query.filter_by(subscription_id=sub.id).order_by(Order.delivery_date).all()

    for i in range(1, len(orders)):
        gap = (orders[i].delivery_date - orders[i - 1].delivery_date).days
        assert gap == 7


def test_create_subscription_biweekly_dates_are_14_days_apart(session):
    client = _make_client(session, 'biweekly_sub')
    monday = datetime.date(2026, 3, 30)
    form = _base_subscription_form(
        first_delivery_date=monday.strftime('%Y-%m-%d'),
        delivery_type='Bi-weekly',
        delivery_day='ПН',
    )

    sub = create_subscription(client, form)
    orders = Order.query.filter_by(subscription_id=sub.id).order_by(Order.delivery_date).all()

    for i in range(1, len(orders)):
        gap = (orders[i].delivery_date - orders[i - 1].delivery_date).days
        assert gap == 14


def test_create_subscription_monthly_dates_are_approx_28_days_apart(session):
    client = _make_client(session, 'monthly_sub')
    monday = datetime.date(2026, 3, 30)
    form = _base_subscription_form(
        first_delivery_date=monday.strftime('%Y-%m-%d'),
        delivery_type='Monthly',
        delivery_day='ПН',
    )

    sub = create_subscription(client, form)
    orders = Order.query.filter_by(subscription_id=sub.id).order_by(Order.delivery_date).all()

    for i in range(1, len(orders)):
        gap = (orders[i].delivery_date - orders[i - 1].delivery_date).days
        assert 25 <= gap <= 31


# ── create_subscription: is_pickup ───────────────────────────────────────────

def test_create_subscription_is_pickup_all_deliveries_no_street(session):
    client = _make_client(session, 'pickup_sub')
    form = _base_subscription_form(is_pickup='on')

    sub = create_subscription(client, form)
    deliveries = Delivery.query.filter_by(client_id=client.id).all()

    for d in deliveries:
        assert d.street is None


# ── create_subscription: time_from/time_to only on first order ───────────────

def test_create_subscription_time_only_on_first_order(session):
    client = _make_client(session, 'time_sub')
    form = _base_subscription_form(time_from='09:00', time_to='12:00')

    sub = create_subscription(client, form)
    orders = Order.query.filter_by(subscription_id=sub.id).order_by(Order.sequence_number).all()

    assert orders[0].time_from == '09:00'
    assert orders[0].time_to == '12:00'
    for order in orders[1:]:
        assert order.time_from is None
        assert order.time_to is None


# ── create_subscription: comment only on first order ─────────────────────────

def test_create_subscription_comment_only_on_first_order(session):
    client = _make_client(session, 'comment_sub')
    form = _base_subscription_form(comment='Тестовий коментар')

    sub = create_subscription(client, form)
    orders = Order.query.filter_by(subscription_id=sub.id).order_by(Order.sequence_number).all()

    assert orders[0].comment == 'Тестовий коментар'
    for order in orders[1:]:
        assert order.comment is None


# ── extend_subscription ──────────────────────────────────────────────────────

def test_extend_subscription_adds_4_more_orders(session):
    client = _make_client(session, 'extend_sub')
    form = _base_subscription_form()
    sub = create_subscription(client, form)

    initial_orders = Order.query.filter_by(subscription_id=sub.id).count()
    assert initial_orders == 4

    extend_subscription(sub)

    total_orders = Order.query.filter_by(subscription_id=sub.id).count()
    assert total_orders == 8


def test_extend_subscription_adds_4_more_deliveries(session):
    client = _make_client(session, 'extend_del_sub')
    form = _base_subscription_form()
    sub = create_subscription(client, form)

    initial_deliveries = Delivery.query.filter_by(client_id=client.id).count()
    assert initial_deliveries == 4

    extend_subscription(sub)

    total_deliveries = Delivery.query.filter_by(client_id=client.id).count()
    assert total_deliveries == 8


def test_extend_subscription_sets_extended_flags(session):
    client = _make_client(session, 'extend_flags')
    form = _base_subscription_form()
    sub = create_subscription(client, form)

    extend_subscription(sub)

    assert sub.is_extended is True
    assert sub.followup_status == 'extended'
    assert sub.planned_contact_date is not None


def test_extend_subscription_new_orders_have_correct_sequence(session):
    client = _make_client(session, 'extend_seq')
    form = _base_subscription_form()
    sub = create_subscription(client, form)

    extend_subscription(sub)
    orders = Order.query.filter_by(subscription_id=sub.id).order_by(Order.sequence_number).all()

    assert len(orders) == 8
    for i, order in enumerate(orders):
        assert order.sequence_number == i + 1


def test_extend_subscription_no_orders_raises_error(session):
    sub = Subscription(
        client_id=1,
        type='Weekly',
        status='active',
        delivery_day='ПН',
        recipient_name='R',
        recipient_phone='+380991234567',
        city='Київ',
        street='Вул. 1',
        size='M',
        for_whom='Я',
    )
    session.add(sub)
    session.commit()

    with pytest.raises(ValueError, match='No orders found'):
        extend_subscription(sub)


# ── create_subscription_from_import ──────────────────────────────────────────

def test_import_subscription_delivery_number_1_creates_4(session):
    client = _make_client(session, 'import_1')
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = FakeForm({
        'recipient_name': 'R',
        'recipient_phone': '+380991234567',
        'first_delivery_date': tomorrow,
        'city': 'Київ',
        'street': 'Вул. 1',
        'size': 'M',
        'for_whom': 'Я',
        'delivery_method': 'courier',
        'delivery_type': 'Weekly',
        'delivery_day': 'ПН',
    })

    sub = create_subscription_from_import(client, form, delivery_number=1)

    orders = Order.query.filter_by(subscription_id=sub.id).all()
    deliveries = Delivery.query.filter_by(client_id=client.id).all()
    assert len(orders) == 4
    assert len(deliveries) == 4


def test_import_subscription_delivery_number_2_creates_3(session):
    client = _make_client(session, 'import_2')
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = FakeForm({
        'recipient_name': 'R',
        'recipient_phone': '+380991234567',
        'first_delivery_date': tomorrow,
        'city': 'Київ',
        'street': 'Вул. 1',
        'size': 'M',
        'for_whom': 'Я',
        'delivery_method': 'courier',
        'delivery_type': 'Weekly',
        'delivery_day': 'ПН',
    })

    sub = create_subscription_from_import(client, form, delivery_number=2)

    orders = Order.query.filter_by(subscription_id=sub.id).all()
    assert len(orders) == 3


def test_import_subscription_delivery_number_3_creates_2(session):
    client = _make_client(session, 'import_3')
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = FakeForm({
        'recipient_name': 'R',
        'recipient_phone': '+380991234567',
        'first_delivery_date': tomorrow,
        'city': 'Київ',
        'street': 'Вул. 1',
        'size': 'M',
        'for_whom': 'Я',
        'delivery_method': 'courier',
        'delivery_type': 'Weekly',
        'delivery_day': 'ПН',
    })

    sub = create_subscription_from_import(client, form, delivery_number=3)

    orders = Order.query.filter_by(subscription_id=sub.id).all()
    assert len(orders) == 2


def test_import_subscription_delivery_number_4_creates_1(session):
    client = _make_client(session, 'import_4')
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = FakeForm({
        'recipient_name': 'R',
        'recipient_phone': '+380991234567',
        'first_delivery_date': tomorrow,
        'city': 'Київ',
        'street': 'Вул. 1',
        'size': 'M',
        'for_whom': 'Я',
        'delivery_method': 'courier',
        'delivery_type': 'Weekly',
        'delivery_day': 'ПН',
    })

    sub = create_subscription_from_import(client, form, delivery_number=4)

    orders = Order.query.filter_by(subscription_id=sub.id).all()
    assert len(orders) == 1


def test_import_subscription_delivery_number_5_creates_reminder_only(session):
    client = _make_client(session, 'import_5')
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = FakeForm({
        'recipient_name': 'R',
        'recipient_phone': '+380991234567',
        'first_delivery_date': tomorrow,
        'city': 'Київ',
        'street': 'Вул. 1',
        'size': 'M',
        'for_whom': 'Я',
        'delivery_method': 'courier',
        'delivery_type': 'Weekly',
        'delivery_day': 'ПН',
    })

    sub = create_subscription_from_import(client, form, delivery_number=5)

    orders = Order.query.filter_by(subscription_id=sub.id).all()
    assert len(orders) == 0
    assert sub.is_renewal_reminder is True
    assert sub.followup_status == 'pending'


# ── delete_subscription ──────────────────────────────────────────────────────

def test_delete_subscription_removes_all_orders_and_deliveries(session):
    client = _make_client(session, 'delete_sub')
    form = _base_subscription_form()
    sub = create_subscription(client, form)

    sub_id = sub.id
    client_id = client.id

    delete_subscription(sub)

    assert Order.query.filter_by(subscription_id=sub_id).count() == 0
    assert Delivery.query.filter_by(client_id=client_id).count() == 0
    assert Subscription.query.get(sub_id) is None


# ── create_draft_subscription ────────────────────────────────────────────────

def test_create_draft_subscription_creates_draft_status(session):
    client = _make_client(session, 'draft_sub')
    contact_date = datetime.date.today()

    sub = create_draft_subscription(client, contact_date)

    assert sub.status == 'draft'
    assert sub.contact_date == contact_date
    assert sub.type == ''
    assert sub.delivery_day == ''


def test_create_draft_subscription_with_optional_fields(session):
    client = _make_client(session, 'draft_sub_opt')
    contact_date = datetime.date.today()

    sub = create_draft_subscription(
        client, contact_date,
        draft_comment='Тестовий коментар',
        draft_bank_link='https://example.com',
        draft_wedding_date=datetime.date(2026, 6, 15),
    )

    assert sub.draft_comment == 'Тестовий коментар'
    assert sub.draft_bank_link == 'https://example.com'
    assert sub.draft_wedding_date == datetime.date(2026, 6, 15)


def test_get_draft_subscriptions_filters_due_contact_dates(session):
    due_client = _make_client(session, 'draft_due')
    future_client = _make_client(session, 'draft_future')
    today = datetime.date.today()

    due_sub = create_draft_subscription(due_client, today - datetime.timedelta(days=1))
    create_draft_subscription(future_client, today + datetime.timedelta(days=2))

    drafts = get_draft_subscriptions(contact_date_to=today)

    assert [sub.id for sub in drafts] == [due_sub.id]
