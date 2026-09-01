"""
Freezing subscription prices (Sept 2026).

Changing prices in the active PricePreset must NOT retroactively re-price
existing orders — subscriptions included. `resolve_charge_amount` returns the
snapshot `order.charged_amount` first, falling back to the live price only when
no snapshot exists.
"""
import datetime

from app.models import Client, Order, Delivery
from app.models.subscription import Subscription
from app.models.settings import Settings
from app.models.price import Price
from app.models.price_preset import PricePreset
from app.models.transaction import Transaction
from app.services.billing_service import resolve_charge_amount, charge_delivery


def _seed_active_preset(session, size_value='M', one_time=999999, subscription=999999):
    size = Settings(type='size', value=size_value)
    session.add(size)
    session.flush()
    preset = PricePreset(name='Основний', is_active=True)
    session.add(preset)
    session.flush()
    session.add(Price(preset_id=preset.id, order_type='one_time', size_id=size.id, price=one_time))
    session.add(Price(preset_id=preset.id, order_type='subscription', size_id=size.id, price=subscription))
    session.commit()
    return preset, size


def _sub_order(session, client, charged_amount):
    sub = Subscription(
        client_id=client.id, type='Weekly', status='active', delivery_day='ПН',
        recipient_name='Отримувач', recipient_phone='+380991234567',
        city='Київ', street='Хрещатик 1', size='M', for_whom='Дружина',
    )
    session.add(sub)
    session.flush()
    o = Order(
        client_id=client.id, subscription_id=sub.id, sequence_number=1,
        recipient_name='Отримувач', recipient_phone='+380991234567',
        city='Київ', street='Хрещатик 1', is_pickup=False, delivery_method='courier',
        size='M', delivery_date=datetime.date.today(), for_whom='Дружина',
        charged_amount=charged_amount,
    )
    session.add(o)
    session.flush()
    d = Delivery(
        order_id=o.id, client_id=client.id, delivery_date=o.delivery_date,
        status='Розподілено', size='M', phone='+380991234567', delivery_method='courier',
    )
    session.add(d)
    session.commit()
    return o, d


def test_frozen_amount_wins_over_changed_preset(app, session):
    client = Client(instagram='freeze_1')
    session.add(client)
    session.commit()
    _seed_active_preset(session, subscription=888800)  # "нова" ціна в довіднику
    order, _ = _sub_order(session, client, charged_amount=1700)

    assert resolve_charge_amount(order) == 1700


def test_falls_back_to_live_price_when_no_snapshot(app, session):
    client = Client(instagram='freeze_2')
    session.add(client)
    session.commit()
    _seed_active_preset(session, subscription=4000)  # 4000 / 4 = 1000 за доставку
    order, _ = _sub_order(session, client, charged_amount=None)

    assert resolve_charge_amount(order) == 1000


def test_charge_delivery_uses_frozen_amount_for_subscription(app, session):
    client = Client(instagram='freeze_3')
    session.add(client)
    session.commit()
    _seed_active_preset(session, subscription=888800)
    order, delivery = _sub_order(session, client, charged_amount=1700)

    txn = charge_delivery(delivery)
    session.commit()

    assert txn is not None
    assert txn.amount == 1700
    assert txn.transaction_type == 'delivery_charge'
