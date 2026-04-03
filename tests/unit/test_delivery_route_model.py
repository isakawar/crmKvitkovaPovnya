"""
Tests for DeliveryRoute model status workflow

Covers:
- DeliveryRoute creation with default status 'draft'
- RouteDelivery creation and linking
- Status transitions: draft -> sent -> accepted
- Status transitions: draft -> sent -> rejected
- Route cascade delete: deleting route deletes stops
- Route with courier vs without courier
- Route stops ordering
"""
import datetime
import pytest
from app.models import Client, Courier, Order, Delivery
from app.models.delivery_route import DeliveryRoute, RouteDelivery


def _make_delivery_with_courier(session):
    client = Client(instagram='route_client')
    courier = Courier(name='Тест Кур', phone='+380991234567', deliveries_count=0)
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
        status='Очікує',
        size='M',
        phone='+380991234567',
        delivery_method='courier',
    )
    session.add(delivery)
    session.commit()
    return delivery, courier


# ── DeliveryRoute creation ───────────────────────────────────────────────────

def test_delivery_route_defaults_to_draft(session):
    route = DeliveryRoute(
        route_date=datetime.date.today(),
    )
    session.add(route)
    session.commit()

    assert route.status == 'draft'
    assert route.courier_id is None
    assert route.deliveries_count == 0


def test_delivery_route_with_courier(session):
    courier = Courier(name='Тест', phone='+380991112233')
    session.add(courier)
    session.commit()

    route = DeliveryRoute(
        courier_id=courier.id,
        route_date=datetime.date.today(),
    )
    session.add(route)
    session.commit()

    assert route.courier_id == courier.id
    assert route.courier.name == 'Тест'


def test_delivery_route_status_transitions(session):
    route = DeliveryRoute(route_date=datetime.date.today(), status='draft')
    session.add(route)
    session.commit()

    route.status = 'sent'
    session.commit()
    assert route.status == 'sent'

    route.status = 'accepted'
    session.commit()
    assert route.status == 'accepted'


def test_delivery_route_rejected_status(session):
    route = DeliveryRoute(route_date=datetime.date.today(), status='draft')
    session.add(route)
    session.commit()

    route.status = 'sent'
    session.commit()

    route.status = 'rejected'
    session.commit()
    assert route.status == 'rejected'


# ── RouteDelivery linking ────────────────────────────────────────────────────

def test_route_delivery_links_route_and_delivery(session):
    delivery, courier = _make_delivery_with_courier(session)

    route = DeliveryRoute(
        courier_id=courier.id,
        route_date=datetime.date.today(),
    )
    session.add(route)
    session.flush()

    stop = RouteDelivery(
        route_id=route.id,
        delivery_id=delivery.id,
        stop_order=1,
    )
    session.add(stop)
    session.commit()

    assert stop.route_id == route.id
    stop.delivery_id == delivery.id
    assert stop.stop_order == 1


def test_route_stops_ordered_by_stop_order(session):
    delivery, courier = _make_delivery_with_courier(session)

    d2 = Delivery(
        order_id=delivery.order_id,
        client_id=delivery.client_id,
        delivery_date=datetime.date.today(),
        status='Очікує',
        size='M',
        phone='+380991234567',
        delivery_method='courier',
    )
    session.add(d2)
    session.commit()

    route = DeliveryRoute(
        courier_id=courier.id,
        route_date=datetime.date.today(),
    )
    session.add(route)
    session.flush()

    s1 = RouteDelivery(route_id=route.id, delivery_id=delivery.id, stop_order=2)
    s2 = RouteDelivery(route_id=route.id, delivery_id=d2.id, stop_order=1)
    session.add_all([s1, s2])
    session.commit()

    stops = RouteDelivery.query.filter_by(route_id=route.id).order_by(RouteDelivery.stop_order).all()
    assert len(stops) == 2
    assert stops[0].stop_order == 1
    assert stops[1].stop_order == 2


# ── Cascade delete ───────────────────────────────────────────────────────────

def test_deleting_route_cascade_deletes_stops(session):
    delivery, courier = _make_delivery_with_courier(session)

    route = DeliveryRoute(
        courier_id=courier.id,
        route_date=datetime.date.today(),
    )
    session.add(route)
    session.flush()

    stop = RouteDelivery(route_id=route.id, delivery_id=delivery.id, stop_order=1)
    session.add(stop)
    session.commit()

    route_id = route.id
    stop_id = stop.id

    session.delete(route)
    session.commit()

    assert DeliveryRoute.query.get(route_id) is None
    assert RouteDelivery.query.get(stop_id) is None


# ── Route metadata fields ────────────────────────────────────────────────────

def test_delivery_route_metadata_fields(session):
    route = DeliveryRoute(
        route_date=datetime.date.today(),
        total_distance_km=15.5,
        estimated_duration_min=45,
        delivery_price=200,
        start_time=datetime.time(9, 0),
    )
    session.add(route)
    session.commit()

    assert route.total_distance_km == 15.5
    assert route.estimated_duration_min == 45
    assert route.delivery_price == 200
    assert route.start_time == datetime.time(9, 0)


def test_delivery_route_telegram_tracking(session):
    route = DeliveryRoute(
        route_date=datetime.date.today(),
        telegram_message_id=12345,
        status='sent',
    )
    session.add(route)
    session.commit()

    assert route.telegram_message_id == 12345
    assert route.status == 'sent'
