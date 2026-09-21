"""Цілісність життєвого циклу замовлення/підписки.

Покриває три місця, де шляхи розходились між собою:
  * charged_amount фіксувався в трьох шляхах створення з чотирьох;
  * update_order не перераховував заморожену ціну (update_subscription — робив);
  * extend_subscription завжди робив 4 доставки, ігноруючи delivery_count;
  * видалення замовлення падало на FK, якщо були фото або сертифікат.
"""
import datetime

import pytest

from app.extensions import db
from app.models import Client, Order, Delivery
from app.models.certificate import Certificate
from app.models.order_photo import OrderPhoto
from app.models.price import Price
from app.models.price_preset import PricePreset
from app.models.settings import Settings
from app.models.subscription import Subscription
from app.services.order_service import delete_order, update_order
from app.services.subscription_service import create_subscription, extend_subscription


def _seed_preset(session, one_time=1000, subscription=4000, size_value='M'):
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


def _client(session, handle):
    c = Client(instagram=handle)
    session.add(c)
    session.commit()
    return c


def _sub_form(**over):
    form = {
        'delivery_type': 'Weekly',
        'delivery_day': 'ПН',
        'first_delivery_date': datetime.date.today().isoformat(),
        'recipient_name': 'Отримувач',
        'recipient_phone': '+380991234567',
        'city': 'Київ',
        'street': 'Хрещатик 1',
        'size': 'M',
        'for_whom': 'Дружина',
    }
    form.update(over)
    return form


# ── charged_amount фіксується при створенні підписки ──────────────────────────

def test_create_subscription_freezes_charged_amount(app, session):
    _seed_preset(session, subscription=4000)
    client = _client(session, 'freeze_sub')

    sub = create_subscription(client, _sub_form())

    orders = Order.query.filter_by(subscription_id=sub.id).all()
    assert len(orders) == 4
    # 4000 за цикл ÷ 4 доставки = 1000 за доставку
    assert all(o.charged_amount == 1000 for o in orders), [o.charged_amount for o in orders]


def test_price_change_does_not_reprice_existing_subscription(app, session):
    preset, size = _seed_preset(session, subscription=4000)
    client = _client(session, 'freeze_sub2')
    sub = create_subscription(client, _sub_form())

    price = Price.query.filter_by(preset_id=preset.id, order_type='subscription').first()
    price.price = 8000
    session.commit()

    from app.services.billing_service import resolve_charge_amount
    for order in Order.query.filter_by(subscription_id=sub.id).all():
        assert resolve_charge_amount(order) == 1000


# ── update_order перераховує заморожену ціну ──────────────────────────────────

def _one_time_order(session, client, size='M', charged_amount=1000):
    order = Order(
        client_id=client.id, recipient_name='Отримувач', recipient_phone='+380991234567',
        city='Київ', street='Хрещатик 1', is_pickup=False, delivery_method='courier',
        size=size, delivery_date=datetime.date.today(), for_whom='Дружина',
        charged_amount=charged_amount,
    )
    session.add(order)
    session.flush()
    delivery = Delivery(
        order_id=order.id, client_id=client.id, delivery_date=order.delivery_date,
        status='Очікує', size=size, phone='+380991234567', delivery_method='courier',
    )
    session.add(delivery)
    session.commit()
    return order, delivery


def test_update_order_recalculates_charged_amount_on_discount_change(app, session):
    _seed_preset(session, one_time=1000)
    client = _client(session, 'reprice_1')
    order, _ = _one_time_order(session, client)

    update_order(order, {
        'first_delivery_date': datetime.date.today().isoformat(),
        'recipient_name': 'Отримувач', 'recipient_phone': '+380991234567',
        'city': 'Київ', 'street': 'Хрещатик 1', 'size': 'M', 'for_whom': 'Дружина',
        'discount': '20',
    })

    assert order.charged_amount == 800


def test_update_order_keeps_price_when_all_deliveries_are_done(app, session):
    """Після списання ціну переписувати не можна — історія розійдеться з фактом."""
    _seed_preset(session, one_time=1000)
    client = _client(session, 'reprice_2')
    order, delivery = _one_time_order(session, client, charged_amount=1000)
    delivery.status = 'Доставлено'
    session.commit()

    update_order(order, {
        'first_delivery_date': datetime.date.today().isoformat(),
        'recipient_name': 'Отримувач', 'recipient_phone': '+380991234567',
        'city': 'Київ', 'street': 'Хрещатик 1', 'size': 'M', 'for_whom': 'Дружина',
        'discount': '50',
    })

    assert order.charged_amount == 1000


# ── extend_subscription поважає delivery_count ────────────────────────────────

@pytest.mark.parametrize('count', [4, 6, 8])
def test_extend_subscription_honours_delivery_count(app, session, count):
    _seed_preset(session)
    client = _client(session, f'extend_{count}')
    sub = create_subscription(client, _sub_form(delivery_count=str(count)))
    assert sub.delivery_count == count

    new_sub = extend_subscription(sub)

    assert new_sub.delivery_count == count
    assert Order.query.filter_by(subscription_id=new_sub.id).count() == count


# ── видалення замовлення з залежностями ───────────────────────────────────────

def test_delete_order_with_photos_does_not_fail(app, session):
    client = _client(session, 'del_photo')
    order, _ = _one_time_order(session, client)
    session.add(OrderPhoto(
        order_id=order.id, filename='x.webp', original_name='x.jpg',
        created_at=datetime.datetime.utcnow(),
    ))
    session.commit()
    order_id = order.id

    delete_order(order)

    assert db.session.get(Order, order_id) is None
    assert OrderPhoto.query.filter_by(order_id=order_id).count() == 0


def test_delete_order_releases_certificate_back_to_active(app, session):
    """Сертифікат — окрема цінність: він відв'язується, а не видаляється."""
    client = _client(session, 'del_cert')
    order, _ = _one_time_order(session, client)
    cert = Certificate(
        code='Р0001', type='amount', value_amount=500,
        expires_at=datetime.date.today() + datetime.timedelta(days=365),
        status='used', order_id=order.id, used_at=datetime.datetime.utcnow(),
    )
    session.add(cert)
    session.commit()
    order_id, cert_id = order.id, cert.id

    delete_order(order)

    assert db.session.get(Order, order_id) is None
    released = db.session.get(Certificate, cert_id)
    assert released is not None
    assert released.order_id is None
    assert released.status == 'active'
    assert released.used_at is None
