"""get_ltv_data — average one-time deliveries per client.

Population: clients with >= 1 non-cancelled one-time delivery
(Order.subscription_id IS NULL). Subscription-only clients are excluded;
a client with both a subscription and a one-time order still counts once.
"""
import datetime

from app.models import Client, Order, Delivery
from app.models.subscription import Subscription
from app.services.reports_service import get_ltv_data


def _one_time_delivery(session, client, status='Доставлено'):
    order = Order(
        client_id=client.id, subscription_id=None,
        recipient_name='Х', recipient_phone='+380000000000',
        city='Київ', street='вул.', size='M', for_whom='Дружина',
        delivery_date=datetime.date.today(),
    )
    session.add(order)
    session.flush()
    session.add(Delivery(order_id=order.id, client_id=client.id,
                         delivery_date=datetime.date.today(), status=status))


def _subscription_delivery(session, client):
    sub = Subscription(
        client_id=client.id, status='active', type='Weekly', delivery_day='ПН',
        recipient_name='Х', recipient_phone='+380000000000',
        city='Київ', street='вул.', size='M', for_whom='Дружина',
    )
    session.add(sub)
    session.flush()
    order = Order(
        client_id=client.id, subscription_id=sub.id,
        recipient_name='Х', recipient_phone='+380000000000',
        city='Київ', street='вул.', size='M', for_whom='Дружина',
        delivery_date=datetime.date.today(),
    )
    session.add(order)
    session.flush()
    session.add(Delivery(order_id=order.id, client_id=client.id,
                         delivery_date=datetime.date.today(), status='Доставлено'))


def test_avg_one_time_deliveries_per_client(app, session):
    # a: only a subscription → excluded from the population
    a = Client(instagram='a', phone='+380990000001')
    # b: two one-time deliveries
    b = Client(instagram='b', phone='+380990000002')
    # c: a subscription AND one one-time delivery → counts as 1 client, 1 delivery
    c = Client(instagram='c', phone='+380990000003')
    # d: one one-time delivery + one cancelled one-time delivery → 1 delivery
    d = Client(instagram='d', phone='+380990000004')
    session.add_all([a, b, c, d])
    session.commit()

    _subscription_delivery(session, a)
    _one_time_delivery(session, b)
    _one_time_delivery(session, b)
    _subscription_delivery(session, c)
    _one_time_delivery(session, c)
    _one_time_delivery(session, d)
    _one_time_delivery(session, d, status='Скасовано')
    session.commit()

    ltv = get_ltv_data()
    # clients b, c, d = 3 ; deliveries 2 + 1 + 1 = 4 → 4/3 = 1.3
    assert ltv['one_time_clients_count'] == 3
    assert ltv['one_time_deliveries_total'] == 4
    assert ltv['avg_one_time_deliveries_per_client'] == round(4 / 3, 1)


def test_avg_one_time_deliveries_zero_when_none(app, session):
    c = Client(instagram='only_sub', phone='+380990000009')
    session.add(c)
    session.commit()
    _subscription_delivery(session, c)
    session.commit()

    ltv = get_ltv_data()
    assert ltv['one_time_clients_count'] == 0
    assert ltv['avg_one_time_deliveries_per_client'] == 0.0
