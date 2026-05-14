from datetime import date, datetime
import json
import logging

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Delivery
from app.models.delivery_route import DeliveryRoute, RouteDelivery

logger = logging.getLogger(__name__)


def save_routes(
    result: dict,
    selected_date: date,
    editing_route_id: int | None = None,
) -> list[DeliveryRoute]:
    """Persist optimized routes for a given date.

    result: full optimizer result dict (contains 'routes' list + metadata).
    For each route in result['routes']:
    - Upserts a DeliveryRoute (creates or updates by routeDbId).
    - Resets old stops and syncs new RouteDelivery records.
    - Transitions delivery statuses: Очікує ↔ Розподілено.
    - Deletes empty routes.

    After processing all routes, removes stale DeliveryRoutes for the date
    that were not included in this save (full-day save mode only).

    Returns the list of saved DeliveryRoute objects.
    """
    routes_data = result.get('routes', [])
    result_meta = {k: v for k, v in result.items() if k != 'routes'}

    # Fallback: match stops by address when optimizer doesn't echo id field
    addr_to_delivery_id = _build_addr_map(selected_date)

    saved_route_ids = []
    _editing_route_id = editing_route_id
    is_single_route_edit = bool(editing_route_id)

    for route_data in routes_data:
        stops = route_data.get('stops', [])

        if not stops:
            empty_route_db_id = route_data.get('routeDbId')
            if empty_route_db_id:
                dr = DeliveryRoute.query.get(empty_route_db_id)
                if dr:
                    _reset_route_deliveries(dr)
                    db.session.delete(dr)
                    db.session.flush()
            continue

        single_route_cache = json.dumps({**result_meta, 'routes': [route_data]})

        route_db_id = route_data.get('routeDbId')
        if not route_db_id and _editing_route_id:
            route_db_id = _editing_route_id
            _editing_route_id = None

        dr = _upsert_delivery_route(route_db_id, route_data, selected_date, stops, single_route_cache)

        for i, stop in enumerate(stops):
            delivery_id = stop.get('id')
            if not delivery_id:
                stop_addr = (stop.get('address') or '').lower().strip()
                delivery_id = addr_to_delivery_id.get(stop_addr)
            if not delivery_id:
                continue

            planned_arrival = _parse_eta(stop.get('eta'), selected_date)
            rd = RouteDelivery(
                route_id=dr.id,
                delivery_id=delivery_id,
                stop_order=i + 1,
                duration_from_previous_min=stop.get('driveMin'),
                planned_arrival=planned_arrival,
            )
            db.session.add(rd)

            delivery = Delivery.query.get(delivery_id)
            if delivery and delivery.status == 'Очікує':
                delivery.status = 'Розподілено'

        saved_route_ids.append(dr.id)

    any_db_id = any(r.get('routeDbId') for r in routes_data)  # noqa: SIM118
    if not is_single_route_edit and any_db_id and saved_route_ids:
        _cleanup_stale_routes(selected_date, saved_route_ids)

    db.session.commit()

    return (
        DeliveryRoute.query
        .filter(DeliveryRoute.id.in_(saved_route_ids))
        .all()
    )


def _build_addr_map(selected_date: date) -> dict:
    """Build address → delivery_id map for fallback matching when stop has no id."""
    deliveries = (
        Delivery.query
        .options(joinedload(Delivery.order))
        .filter(Delivery.delivery_date == selected_date)
        .all()
    )
    addr_map = {}
    for d in deliveries:
        order = d.order
        city = (order.city if order else '') or ''
        street = (d.street or (order.street if order else '')) or ''
        house = (d.building_number or (order.building_number if order else '')) or ''
        parts = []
        if city:
            parts.append(city)
        if street:
            parts.append(street + (' ' + house if house else ''))
        key = ', '.join(parts).lower().strip()
        if key:
            addr_map[key] = d.id
    return addr_map


def _upsert_delivery_route(route_db_id, route_data, selected_date, stops, cached_json):
    dep_str = (route_data.get('departureTime') or '').strip()
    start_time = _parse_time(dep_str)

    if route_db_id:
        dr = DeliveryRoute.query.get(route_db_id)
        if dr:
            _reset_route_deliveries(dr)
            dr.route_date = selected_date
            dr.deliveries_count = len(stops)
            dr.total_distance_km = route_data.get('totalDistanceKm')
            dr.estimated_duration_min = route_data.get('totalDriveMin')
            dr.cached_result_json = cached_json
            dr.cached_at = datetime.utcnow()
            dr.content_changed_at = datetime.utcnow()
            if start_time:
                dr.start_time = start_time
            db.session.flush()
            return dr

    dr = DeliveryRoute(
        route_date=selected_date,
        status='draft',
        deliveries_count=len(stops),
        total_distance_km=route_data.get('totalDistanceKm'),
        estimated_duration_min=route_data.get('totalDriveMin'),
        start_time=start_time,
        cached_result_json=cached_json,
        cached_at=datetime.utcnow(),
    )
    db.session.add(dr)
    db.session.flush()
    return dr


def _reset_route_deliveries(dr: DeliveryRoute):
    old_delivery_ids = [s.delivery_id for s in dr.stops]
    if old_delivery_ids:
        Delivery.query.filter(Delivery.id.in_(old_delivery_ids)).update(
            {'status': 'Очікує'}, synchronize_session=False
        )
    RouteDelivery.query.filter_by(route_id=dr.id).delete()


def _cleanup_stale_routes(selected_date: date, saved_route_ids: list):
    stale_routes = DeliveryRoute.query.filter(
        DeliveryRoute.route_date == selected_date,
        ~DeliveryRoute.id.in_(saved_route_ids),
    ).all()
    for stale in stale_routes:
        _reset_route_deliveries(stale)
        db.session.delete(stale)
        logger.info('save_routes: deleted stale route id=%d', stale.id)


def _parse_eta(eta_str: str | None, selected_date: date) -> datetime | None:
    if not eta_str:
        return None
    try:
        return datetime.strptime(f'{selected_date.isoformat()} {eta_str}', '%Y-%m-%d %H:%M')
    except ValueError:
        return None


def _parse_time(time_str: str) -> object | None:
    if not time_str:
        return None
    try:
        return datetime.strptime(time_str, '%H:%M').time()
    except ValueError:
        return None
