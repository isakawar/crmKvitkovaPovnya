"""get_dashboard_kpis — the hero cards above the report tabs."""
import datetime

from app.models import Client, Order, Delivery
from app.models.subscription import Subscription
from app.services.reports_service import get_dashboard_kpis


def _new_sub(client, status):
    return Subscription(
        client_id=client.id, status=status, type='Weekly', delivery_day='ПН',
        recipient_name='Х', recipient_phone='+380000000000',
        city='Київ', street='вул.', size='M', for_whom='Дружина',
    )


def _sub_with_delivery(session, client, sub_status, delivery_status):
    sub = _new_sub(client, sub_status)
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
    session.add(Delivery(
        order_id=order.id, client_id=client.id,
        delivery_date=datetime.date.today(), status=delivery_status,
    ))
    session.commit()
    return sub


def test_active_subscriptions_counts_only_those_with_a_pending_delivery(app, session):
    client = Client(instagram='c1', phone='+380991110000')
    session.add(client)
    session.commit()

    # counts: active + has a not-yet-delivered delivery
    _sub_with_delivery(session, client, 'active', 'Очікує')
    _sub_with_delivery(session, client, 'active', 'Розподілено')
    # does NOT count: active but every delivery is terminal
    _sub_with_delivery(session, client, 'active', 'Доставлено')
    _sub_with_delivery(session, client, 'active', 'Скасовано')
    # does NOT count: pending delivery but subscription itself not active
    _sub_with_delivery(session, client, 'completed', 'Очікує')
    _sub_with_delivery(session, client, 'draft', 'Очікує')

    kpis = get_dashboard_kpis()
    assert kpis['active_subscriptions'] == 2


def test_active_subscription_counted_once_despite_multiple_pending_deliveries(app, session):
    client = Client(instagram='c2', phone='+380991110001')
    session.add(client)
    session.commit()
    sub = _new_sub(client, 'active')
    session.add(sub)
    session.flush()
    for _ in range(3):
        order = Order(
            client_id=client.id, subscription_id=sub.id,
            recipient_name='Х', recipient_phone='+380000000000',
            city='Київ', street='вул.', size='M', for_whom='Дружина', delivery_date=datetime.date.today(),
        )
        session.add(order)
        session.flush()
        session.add(Delivery(order_id=order.id, client_id=client.id,
                             delivery_date=datetime.date.today(), status='Очікує'))
    session.commit()

    assert get_dashboard_kpis()['active_subscriptions'] == 1


def test_monthly_trend_excludes_draft_subscriptions(app, session):
    """The 'Динаміка нових замовлень / підписок' chart must match the hero card:
    a draft subscription is not a new subscription."""
    from app.services.reports_service import _monthly_orders_trend

    client = Client(instagram='c3', phone='+380991110002')
    session.add(client)
    session.commit()

    session.add(_new_sub(client, 'active'))
    session.add(_new_sub(client, 'active'))
    session.add(_new_sub(client, 'draft'))
    session.commit()

    trend = _monthly_orders_trend()
    assert sum(trend['subscriptions_values']) == 2
