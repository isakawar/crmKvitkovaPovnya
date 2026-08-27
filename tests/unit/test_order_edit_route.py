"""
Tests for GET /orders/<id>/edit — the payload that pre-fills the edit modal.

Covers:
- time_from / time_to fall back to the first pending delivery when the order
  itself has no time (time is often set delivery-only via the inline widget),
  so re-saving the modal does not wipe it.
"""
import datetime

from app.models import Client, Order, Delivery


def _make_order(session, *, order_time=(None, None), delivery_time=(None, None)):
    client = Client(instagram='edit_route_client')
    session.add(client)
    session.flush()

    order = Order(
        client_id=client.id,
        recipient_name='Тест',
        recipient_phone='+380991234567',
        city='Київ',
        street='Хрещатик 1',
        size='M',
        delivery_date=datetime.date.today(),
        for_whom='Дружина',
        delivery_method='courier',
        time_from=order_time[0],
        time_to=order_time[1],
    )
    session.add(order)
    session.flush()

    delivery = Delivery(
        order_id=order.id,
        client_id=client.id,
        delivery_date=datetime.date.today(),
        status='Очікує',
        size='M',
        phone='+380991234567',
        delivery_method='courier',
        street='Хрещатик 1',
        time_from=delivery_time[0],
        time_to=delivery_time[1],
    )
    session.add(delivery)
    session.commit()
    return order


def test_order_edit_get_uses_delivery_time_when_order_has_none(app, session):
    order = _make_order(session, order_time=(None, None), delivery_time=('10:00', '14:00'))

    resp = app.test_client().get(f'/orders/{order.id}/edit')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['time_from'] == '10:00'
    assert data['time_to'] == '14:00'


def test_order_edit_get_prefers_delivery_time_over_stale_order_time(app, session):
    """The inline time widget writes only the delivery, so the delivery value is
    the authoritative one to show in the modal."""
    order = _make_order(session, order_time=('09:00', '11:00'), delivery_time=('10:00', '14:00'))

    resp = app.test_client().get(f'/orders/{order.id}/edit')
    data = resp.get_json()
    assert data['time_from'] == '10:00'
    assert data['time_to'] == '14:00'


def test_order_edit_get_falls_back_to_order_time_when_delivery_has_none(app, session):
    order = _make_order(session, order_time=('09:00', '11:00'), delivery_time=(None, None))

    resp = app.test_client().get(f'/orders/{order.id}/edit')
    data = resp.get_json()
    assert data['time_from'] == '09:00'
    assert data['time_to'] == '11:00'
