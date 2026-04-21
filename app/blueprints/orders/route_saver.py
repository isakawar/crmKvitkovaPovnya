import logging
import json

from flask import request, jsonify, current_app
from flask_login import login_required
from sqlalchemy.orm import joinedload
from datetime import date, datetime

from app.blueprints.orders.routes import orders_bp
from app.extensions import db
from app.models import Delivery
from app.models.delivery_route import DeliveryRoute, RouteDelivery

logger = logging.getLogger(__name__)


@orders_bp.route('/route-generator/save', methods=['POST'])
@login_required
def route_generator_save():
    data = request.get_json(silent=True) or {}
    result_json = data.get('result_json', '')
    selected_date_str = data.get('selected_date', date.today().isoformat())

    try:
        result = json.loads(result_json) if isinstance(result_json, str) else result_json
    except (json.JSONDecodeError, ValueError):
        return jsonify({'error': 'Некоректний JSON'}), 400

    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Некоректна дата'}), 400

    routes = result.get('routes', [])
    current_app.logger.info('SAVE_ROUTES: received %d routes: %s', len(routes), [
        {'routeDbId': r.get('routeDbId'), 'stops_count': len(r.get('stops', []))} for r in routes
    ])
    if not routes:
        return jsonify({'error': 'Немає маршрутів для збереження'}), 400

    day_deliveries = (
        Delivery.query
        .options(joinedload(Delivery.order))
        .filter(Delivery.delivery_date == selected_date)
        .all()
    )
    addr_to_delivery_id = {}
    for d in day_deliveries:
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
            addr_to_delivery_id[key] = d.id

    editing_route_id = data.get('editing_route_id')
    saved_route_ids = []

    for route_data in routes:
        stops = route_data.get('stops', [])
        if not stops:
            # If this was an existing DB route that is now empty, delete it
            empty_route_db_id = route_data.get('routeDbId')
            if empty_route_db_id:
                dr_to_delete = DeliveryRoute.query.get(empty_route_db_id)
                if dr_to_delete:
                    old_delivery_ids = [s.delivery_id for s in dr_to_delete.stops]
                    if old_delivery_ids:
                        Delivery.query.filter(Delivery.id.in_(old_delivery_ids)).update(
                            {'status': 'Очікує'}, synchronize_session=False
                        )
                    db.session.delete(dr_to_delete)
                    db.session.flush()
            continue

        single_route_cache = json.dumps({
            **{k: v for k, v in result.items() if k != 'routes'},
            'routes': [route_data],
        })

        dr = None
        # Per-route routeDbId takes priority (view_date multi-edit mode)
        route_db_id = route_data.get('routeDbId')
        # Fallback: legacy single editing_route_id (consumed once)
        if not route_db_id and editing_route_id:
            route_db_id = editing_route_id
            editing_route_id = None
        if route_db_id:
            dr = DeliveryRoute.query.get(route_db_id)
            if dr:
                old_delivery_ids = [s.delivery_id for s in dr.stops]
                if old_delivery_ids:
                    Delivery.query.filter(Delivery.id.in_(old_delivery_ids)).update(
                        {'status': 'Очікує'}, synchronize_session=False
                    )
                RouteDelivery.query.filter_by(route_id=dr.id).delete()
                dr.route_date = selected_date
                dr.deliveries_count = len(stops)
                dr.total_distance_km = route_data.get('totalDistanceKm')
                dr.estimated_duration_min = route_data.get('totalDriveMin')
                dr.cached_result_json = single_route_cache
                dr.cached_at = datetime.utcnow()
                dep_str = (route_data.get('departureTime') or '').strip()
                if dep_str:
                    try:
                        dr.start_time = datetime.strptime(dep_str, '%H:%M').time()
                    except ValueError:
                        logger.warning('Invalid departure time %r, skipping', dep_str)
                db.session.flush()
            else:
                dr = None

        if not dr:
            start_time_val = None
            dep_str = (route_data.get('departureTime') or '').strip()
            if dep_str:
                try:
                    start_time_val = datetime.strptime(dep_str, '%H:%M').time()
                except ValueError:
                    logger.warning('Invalid departure time %r, skipping', dep_str)
            dr = DeliveryRoute(
                route_date=selected_date,
                status='draft',
                deliveries_count=len(stops),
                total_distance_km=route_data.get('totalDistanceKm'),
                estimated_duration_min=route_data.get('totalDriveMin'),
                start_time=start_time_val,
                cached_result_json=single_route_cache,
                cached_at=datetime.utcnow(),
            )
            db.session.add(dr)
            db.session.flush()

        for i, stop in enumerate(stops):
            delivery_id = stop.get('id')
            if not delivery_id:
                stop_addr = (stop.get('address') or '').lower().strip()
                delivery_id = addr_to_delivery_id.get(stop_addr)
            if not delivery_id:
                continue

            planned_arrival = None
            if stop.get('eta'):
                try:
                    planned_arrival = datetime.strptime(
                        f"{selected_date_str} {stop['eta']}", '%Y-%m-%d %H:%M'
                    )
                except ValueError:
                    logger.warning('Invalid ETA value %r, skipping planned_arrival', stop.get('eta'))

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

    # Clean up routes for this date that existed before but were not included in the save
    # (handles the case where a courier's route became empty and the frontend omitted it entirely)
    any_db_id = any(r.get('routeDbId') for r in routes)
    if any_db_id and saved_route_ids:
        stale_routes = DeliveryRoute.query.filter(
            DeliveryRoute.route_date == selected_date,
            ~DeliveryRoute.id.in_(saved_route_ids)
        ).all()
        for stale in stale_routes:
            old_delivery_ids = [s.delivery_id for s in stale.stops]
            if old_delivery_ids:
                Delivery.query.filter(Delivery.id.in_(old_delivery_ids)).update(
                    {'status': 'Очікує'}, synchronize_session=False
                )
            db.session.delete(stale)
            current_app.logger.info('SAVE_ROUTES: deleted stale route id=%d (not in saved set)', stale.id)

    db.session.commit()

    saved_routes_list = (
        DeliveryRoute.query
        .filter(DeliveryRoute.id.in_(saved_route_ids))
        .options(joinedload(DeliveryRoute.courier))
        .all()
    )
    return jsonify({
        'success': True,
        'route_ids': saved_route_ids,
        'count': len(saved_route_ids),
        'editing_route_id': editing_route_id,
        'saved_routes': [{
            'id': dr.id,
            'courier_id': dr.courier_id,
            'courier_name': dr.courier.name if dr.courier else None,
            'courier_has_telegram': bool(dr.courier and dr.courier.telegram_chat_id),
            'deliveries_count': dr.deliveries_count,
            'status': dr.status,
        } for dr in saved_routes_list],
    })
