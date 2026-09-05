"""
Tests for app/services/route_service.py

Covers:
- save_routes: new route is created with correct stops
- save_routes: deliveries transition Очікує → Розподілено
- save_routes: re-save updates existing route, does not duplicate
- save_routes: re-save resets old delivery statuses to Очікує before reassigning
- save_routes: empty route (no stops) is deleted from DB
- save_routes: stale routes for the day are cleaned up
- save_routes: fallback address matching when stop has no id
- save_routes: editing_route_id targets only one route, leaves others intact
- delete_route endpoint: resets delivery statuses to Очікує on delete
"""
import datetime

from app.models import Client, Order, Delivery
from app.models.delivery_route import DeliveryRoute, RouteDelivery
from app.services.route_service import save_routes


TODAY = datetime.date.today()


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_delivery(session, *, city='Київ', street='Хрещатик', building='1',
                   status='Очікує', delivery_date=None):
    client = Client(instagram=f'cli_{street}_{building}_{id(session)}')
    session.add(client)
    session.flush()

    order = Order(
        client_id=client.id,
        recipient_name='R',
        recipient_phone='+380991234567',
        city=city,
        street=street,
        building_number=building,
        size='M',
        delivery_date=delivery_date or TODAY,
        for_whom='Я',
        delivery_method='courier',
    )
    session.add(order)
    session.flush()

    delivery = Delivery(
        order_id=order.id,
        client_id=client.id,
        delivery_date=delivery_date or TODAY,
        status=status,
        size='M',
        phone='+380991234567',
        delivery_method='courier',
    )
    session.add(delivery)
    session.commit()
    return delivery


def _result(deliveries, *, route_db_id=None, distance=10.0, drive_min=30):
    """Build a minimal optimizer result dict for the given delivery list."""
    stops = [
        {
            'id': d.id,
            'address': f'{d.order.city}, {d.order.street} {d.order.building_number}',
            'eta': '10:00',
            'driveMin': drive_min // len(deliveries),
        }
        for d in deliveries
    ]
    route = {
        'stops': stops,
        'totalDistanceKm': distance,
        'totalDriveMin': drive_min,
        'departureTime': '09:00',
    }
    if route_db_id:
        route['routeDbId'] = route_db_id
    return {'routes': [route]}


def _empty_result(route_db_id):
    """Build an optimizer result for an existing route with no stops (triggers deletion)."""
    return {'routes': [{'routeDbId': route_db_id, 'stops': []}]}


def _addr_result(*addresses):
    """Build an optimizer result where stops have only addresses (no delivery id) for fallback tests."""
    stops = [{'address': addr, 'eta': '11:00', 'driveMin': 10} for addr in addresses]
    return {'routes': [{'stops': stops, 'totalDistanceKm': 3.0, 'totalDriveMin': 15, 'departureTime': '10:00'}]}


def _multi_result(route_specs):
    """Build an optimizer result with several routes in one payload.

    route_specs: list of (deliveries, route_db_id_or_None) tuples. Passing the
    same route_db_id twice reproduces a payload where one route appears more
    than once in the same save request.
    """
    routes = []
    for deliveries, route_db_id in route_specs:
        stops = [
            {
                'id': d.id,
                'address': f'{d.order.city}, {d.order.street} {d.order.building_number}',
                'eta': '10:00',
                'driveMin': 5,
            }
            for d in deliveries
        ]
        route = {'stops': stops, 'totalDistanceKm': 5.0, 'totalDriveMin': 10, 'departureTime': '09:00'}
        if route_db_id:
            route['routeDbId'] = route_db_id
        routes.append(route)
    return {'routes': routes}


# ── 1. New route is created with correct stops ────────────────────────────────

def test_save_routes_creates_delivery_route_and_stops(session):
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')

    result = save_routes(_result([d1, d2]), TODAY)

    assert len(result) == 1
    route = result[0]
    assert route.deliveries_count == 2
    assert len(route.stops) == 2
    stop_delivery_ids = {s.delivery_id for s in route.stops}
    assert d1.id in stop_delivery_ids
    assert d2.id in stop_delivery_ids


def test_save_routes_stop_order_is_sequential(session):
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')

    route = save_routes(_result([d1, d2]), TODAY)[0]

    orders = sorted(s.stop_order for s in route.stops)
    assert orders == [1, 2]


def test_save_routes_stores_distance_and_duration(session):
    d = _make_delivery(session)

    route = save_routes(_result([d], distance=12.5, drive_min=40), TODAY)[0]

    assert route.total_distance_km == 12.5
    assert route.estimated_duration_min == 40


def test_save_routes_stores_start_time(session):
    d = _make_delivery(session)

    route = save_routes(_result([d]), TODAY)[0]

    assert route.start_time == datetime.time(9, 0)


# ── 2. Deliveries transition Очікує → Розподілено ────────────────────────────

def test_save_routes_sets_status_rozpodileno(session):
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')
    assert d1.status == 'Очікує'
    assert d2.status == 'Очікує'

    save_routes(_result([d1, d2]), TODAY)

    session.refresh(d1)
    session.refresh(d2)
    assert d1.status == 'Розподілено'
    assert d2.status == 'Розподілено'


def test_save_routes_does_not_change_already_delivered_status(session):
    d = _make_delivery(session, status='Доставлено')

    save_routes(_result([d]), TODAY)

    session.refresh(d)
    assert d.status == 'Доставлено'


# ── 3. Re-save updates existing route, does not duplicate ────────────────────

def test_save_routes_resave_updates_not_duplicates(session):
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')

    first = save_routes(_result([d1, d2]), TODAY)[0]
    route_id = first.id

    updated = save_routes(_result([d1, d2], route_db_id=route_id), TODAY)[0]

    total = DeliveryRoute.query.count()
    assert total == 1
    assert updated.id == route_id


def test_save_routes_resave_updates_deliveries_count(session):
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')
    d3 = _make_delivery(session, street='Вул. В', building='3')

    first = save_routes(_result([d1, d2]), TODAY)[0]
    route_id = first.id
    assert first.deliveries_count == 2

    updated = save_routes(_result([d1, d2, d3], route_db_id=route_id), TODAY)[0]

    assert updated.deliveries_count == 3


# ── 4. Re-save resets old delivery statuses before reassigning ────────────────

def test_save_routes_resave_resets_removed_delivery_to_ochikuye(session):
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')

    first = save_routes(_result([d1, d2]), TODAY)[0]
    route_id = first.id

    # Re-save with only d1; d2 should be reset to Очікує
    save_routes(_result([d1], route_db_id=route_id), TODAY)

    session.refresh(d2)
    assert d2.status == 'Очікує'


def test_save_routes_resave_old_stops_are_replaced(session):
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')

    first = save_routes(_result([d1, d2]), TODAY)[0]
    route_id = first.id

    save_routes(_result([d1], route_db_id=route_id), TODAY)

    stop_count = RouteDelivery.query.filter_by(route_id=route_id).count()
    assert stop_count == 1


# ── 5. Empty route (no stops) is deleted from DB ─────────────────────────────

def test_save_routes_empty_route_is_deleted(session):
    d = _make_delivery(session)

    first = save_routes(_result([d]), TODAY)[0]
    route_id = first.id

    save_routes(_empty_result(route_id), TODAY)

    assert DeliveryRoute.query.get(route_id) is None


def test_save_routes_empty_route_resets_delivery_status(session):
    d = _make_delivery(session)

    first = save_routes(_result([d]), TODAY)[0]
    route_id = first.id

    save_routes(_empty_result(route_id), TODAY)

    session.refresh(d)
    assert d.status == 'Очікує'


# ── 6. Stale routes for the day are cleaned up ───────────────────────────────

def test_save_routes_removes_stale_routes(session):
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')

    # Create two separate routes for the same day (without routeDbId → no cleanup triggered yet)
    r1 = save_routes(_result([d1]), TODAY)[0]
    r2 = save_routes(_result([d2]), TODAY)[0]
    assert DeliveryRoute.query.count() == 2

    # Full-day re-save: only r1 is present and carries its routeDbId.
    # _cleanup_stale_routes fires because any_db_id=True and it's not a single-route edit.
    save_routes(_result([d1], route_db_id=r1.id), TODAY)

    assert DeliveryRoute.query.get(r1.id) is not None
    assert DeliveryRoute.query.get(r2.id) is None


def test_save_routes_stale_cleanup_resets_delivery_status(session):
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')

    r1 = save_routes(_result([d1]), TODAY)[0]
    save_routes(_result([d2]), TODAY)

    session.refresh(d2)
    assert d2.status == 'Розподілено'

    # Full-day save keeps only r1
    save_routes(_result([d1], route_db_id=r1.id), TODAY)

    session.refresh(d2)
    assert d2.status == 'Очікує'


# ── 7. Fallback: address matching when stop has no id ────────────────────────

def test_save_routes_fallback_matches_by_address(session):
    d = _make_delivery(session, city='Київ', street='Садова', building='10')

    routes = save_routes(_addr_result('Київ, Садова 10'), TODAY)

    assert len(routes) == 1
    assert len(routes[0].stops) == 1
    assert routes[0].stops[0].delivery_id == d.id


def test_save_routes_fallback_sets_status_rozpodileno(session):
    d = _make_delivery(session, city='Київ', street='Садова', building='10')

    save_routes(_addr_result('Київ, Садова 10'), TODAY)

    session.refresh(d)
    assert d.status == 'Розподілено'


def test_save_routes_fallback_unknown_address_stop_is_skipped(session):
    result = _addr_result('Київ, Невідома вул. 999')
    # No deliveries in DB → address won't match → route created but with 0 stops
    # (the empty route guard only triggers when routeDbId exists — new routes are kept)
    routes = save_routes(result, TODAY)
    # Route is still created (stops list in data was non-empty), but no RouteDelivery records
    if routes:
        assert RouteDelivery.query.filter_by(route_id=routes[0].id).count() == 0


# ── 8. editing_route_id targets only one route, leaves others intact ──────────

def test_save_routes_editing_route_id_does_not_touch_other_routes(session):
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')

    r1 = save_routes(_result([d1]), TODAY)[0]
    r2 = save_routes(_result([d2]), TODAY)[0]

    # Edit only r1 (no routeDbId in stops, but editing_route_id provided)
    save_routes(_result([d1]), TODAY, editing_route_id=r1.id)

    # r2 must still exist
    assert DeliveryRoute.query.get(r2.id) is not None


def test_save_routes_editing_route_id_updates_correct_route(session):
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')

    r1 = save_routes(_result([d1]), TODAY)[0]
    r1_id = r1.id

    updated = save_routes(_result([d1, d2]), TODAY, editing_route_id=r1_id)[0]

    assert updated.id == r1_id
    assert updated.deliveries_count == 2


# ── 9. DELETE /routes/<id>/delete endpoint ───────────────────────────────────

def _authed_client(app, session):
    from app.models.user import User
    manager = User(email='mgr@test.com', username='mgr', user_type='manager', is_active=True)
    manager.set_password('secret')
    session.add(manager)
    session.commit()
    tc = app.test_client()
    with tc.session_transaction() as flask_session:
        flask_session['_user_id'] = str(manager.id)
        flask_session['_fresh'] = True
    return tc


def test_delete_route_endpoint_resets_deliveries_to_ochikuye(app, session):
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')

    route = save_routes(_result([d1, d2]), TODAY)[0]
    session.refresh(d1)
    session.refresh(d2)
    assert d1.status == 'Розподілено'
    assert d2.status == 'Розподілено'

    resp = _authed_client(app, session).post(f'/routes/{route.id}/delete')

    assert resp.status_code in (200, 302)
    session.expire_all()
    assert d1.status == 'Очікує'
    assert d2.status == 'Очікує'


def test_delete_route_endpoint_removes_route_and_stops(app, session):
    d = _make_delivery(session)
    route = save_routes(_result([d]), TODAY)[0]
    route_id = route.id

    resp = _authed_client(app, session).post(f'/routes/{route_id}/delete')

    assert resp.status_code in (200, 302)
    session.expire_all()
    assert DeliveryRoute.query.filter_by(id=route_id).first() is None
    assert RouteDelivery.query.filter_by(route_id=route_id).count() == 0


# ── 10. Incident 2026-09-05 — regression tests reproducing the production bug ─
#
# Root cause: _cleanup_stale_routes() (and the per-route loop itself) trusts
# the routes array from a single save_routes() call as if it were a complete,
# intentional snapshot of the whole day. It has no way to tell "the user
# deleted this route on purpose" apart from "this route was never part of
# what the caller was looking at". See tasks/ for the incident writeup.

def test_incident_resave_of_newly_created_route_wipes_unrelated_routes(session):
    """07:08:52 and 07:49:47 UTC on 2026-09-05: a manager distributes one new
    delivery into a brand-new route (1st save: no routeDbId yet, cleanup does
    not run). Anything that saves that same 1-route view again (double
    submit, going back to the same page) now carries a routeDbId, so
    _cleanup_stale_routes used to treat "1 route in this payload" as "the
    whole day" and delete every other real route for the date.

    Fixed via known_route_ids: a session that only ever saw the one route it
    just distributed reports that as its known set, so cleanup has no basis
    to touch r1/r2 even though they are absent from the payload."""
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')
    d3 = _make_delivery(session, street='Вул. В', building='3')

    r1 = save_routes(_result([d1]), TODAY)[0]
    r2 = save_routes(_result([d2]), TODAY)[0]

    # A new delivery gets distributed into a brand-new route (1st save). This
    # session never saw r1/r2, so its known set starts out empty.
    new_route = save_routes(_result([d3]), TODAY, known_route_ids=[])[0]

    # The same "just distributed" view is saved a second time; the frontend
    # now knows about the route id the first save returned.
    save_routes(_result([d3], route_db_id=new_route.id), TODAY, known_route_ids=[new_route.id])

    assert DeliveryRoute.query.get(r1.id) is not None, \
        'unrelated route wiped by resaving an unrelated single new route'
    assert DeliveryRoute.query.get(r2.id) is not None, \
        'unrelated route wiped by resaving an unrelated single new route'


def test_incident_stale_full_day_snapshot_wipes_routes_created_elsewhere(session):
    """07:41:20 and 07:48:11 UTC on 2026-09-05: routes created via one
    action (e.g. a second browser tab, or the distribute banner) after a
    generator page already loaded its "full day" snapshot used to get
    deleted when that stale snapshot was later saved via the ordinary
    full-day save, because save_routes() had no way to know those new routes
    were never part of what that page loaded.

    Fixed via known_route_ids: the stale session only reports r1/r2 (what it
    actually rendered), so r3 — created after that render, elsewhere — is
    never a cleanup candidate."""
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')
    d3 = _make_delivery(session, street='Вул. В', building='3')

    r1 = save_routes(_result([d1]), TODAY)[0]
    r2 = save_routes(_result([d2]), TODAY)[0]

    # A route created independently (e.g. another tab distributing a new
    # delivery) after the "stale" full-day view above was already loaded.
    r3 = save_routes(_result([d3]), TODAY)[0]

    # The stale full-day view (only ever rendered r1, r2) gets saved.
    save_routes(
        _multi_result([([d1], r1.id), ([d2], r2.id)]), TODAY,
        known_route_ids=[r1.id, r2.id],
    )

    assert DeliveryRoute.query.get(r3.id) is not None, \
        'route created elsewhere wiped by an unrelated stale full-day save'


def test_incident_duplicate_route_entry_in_one_payload_rejected(session):
    """07:35:03 UTC on 2026-09-05: the same routeDbId appeared twice in a
    single /route-generator/save payload (route 605 logged as edited with 4
    stops, then immediately again with 1 stop, same request). The per-route
    loop in save_routes() used to reset and rebuild stops for every
    occurrence, so the last occurrence silently overwrote the first — inside
    one call, with no stale-route cleanup involved at all.

    Fixed by rejecting a payload with a duplicate routeDbId outright (a
    shape that can only come from corrupted client state) instead of
    guessing which occurrence should win."""
    d1 = _make_delivery(session, street='Вул. А', building='1')
    d2 = _make_delivery(session, street='Вул. Б', building='2')
    d3 = _make_delivery(session, street='Вул. В', building='3')

    route = save_routes(_result([d1, d2, d3]), TODAY)[0]
    route_id = route.id

    # Same routeDbId referenced twice in one payload — mirrors the duplicate
    # "edit route 605" activity-log entries from the same request.
    import pytest
    with pytest.raises(ValueError):
        save_routes(_multi_result([
            ([d1, d2, d3], route_id),
            ([d1], route_id),
        ]), TODAY)

    # Nothing should have been touched — the payload is rejected up front.
    session.refresh(d2)
    session.refresh(d3)
    assert d2.status == 'Розподілено'
    assert d3.status == 'Розподілено'
    assert RouteDelivery.query.filter_by(route_id=route_id).count() == 3
