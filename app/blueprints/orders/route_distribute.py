import logging
import json

from flask import render_template, request, jsonify, current_app
from flask_login import login_required
from sqlalchemy.orm import joinedload
from datetime import date, datetime

from app.blueprints.orders import orders_bp
from app.extensions import db
from app.models import Delivery
from app.models.delivery_route import DeliveryRoute, RouteDelivery
from app.models.courier import Courier
from app.services.route_optimizer_service import (
    distribute_deliveries,
    RouteOptimizerError,
    RouteOptimizerInfeasibleError,
)

logger = logging.getLogger(__name__)


@orders_bp.route('/route-generator/distribute', methods=['GET'])
@login_required
def route_generator_distribute_page():
    date_str = request.args.get('date', date.today().isoformat())
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = date.today()
        date_str = selected_date.isoformat()

    saved_routes = (
        DeliveryRoute.query
        .options(
            joinedload(DeliveryRoute.stops).joinedload(RouteDelivery.delivery).joinedload(Delivery.order),
            joinedload(DeliveryRoute.courier),
        )
        .filter(DeliveryRoute.route_date == selected_date)
        .all()
    )

    already_routed = db.session.query(RouteDelivery.delivery_id).scalar_subquery()
    unrouted = (
        Delivery.query
        .options(joinedload(Delivery.order), joinedload(Delivery.client))
        .filter(
            Delivery.delivery_date == selected_date,
            Delivery.is_pickup == False,
            Delivery.delivery_method != 'nova_poshta',
            Delivery.status.in_(['Очікує', 'Розподілено']),
            ~Delivery.id.in_(already_routed),
        )
        .order_by(Delivery.time_from.asc().nullslast(), Delivery.id.asc())
        .all()
    )

    return render_template(
        'routes/distribute.html',
        saved_routes=saved_routes,
        unrouted_deliveries=unrouted,
        selected_date=selected_date,
        date_str=date_str,
    )


@orders_bp.route('/route-generator/distribute', methods=['POST'])
@login_required
def route_generator_distribute():
    data = request.get_json(silent=True) or {}
    route_ids = [int(x) for x in data.get('route_ids', [])]
    delivery_ids = [int(x) for x in data.get('delivery_ids', [])]

    if not route_ids or not delivery_ids:
        return jsonify({'error': 'Оберіть маршрути та доставки'}), 400

    optimizer_url = current_app.config.get('ROUTE_OPTIMIZER_URL', 'http://localhost:8000')
    try:
        result = distribute_deliveries(route_ids, delivery_ids, optimizer_url)
    except RouteOptimizerInfeasibleError as e:
        return jsonify({'error': str(e)}), 422
    except RouteOptimizerError as e:
        return jsonify({'error': str(e)}), 502

    # Restore routeDbId, courierName, and depot (optimizer may strip them)
    route_map = {r.id: r for r in DeliveryRoute.query.filter(DeliveryRoute.id.in_(route_ids)).options(
        joinedload(DeliveryRoute.courier)
    ).all()}
    for route_data in result.get('routes', []):
        db_id = route_data.get('routeDbId')
        if db_id and db_id in route_map:
            dr = route_map[db_id]
            route_data['routeDbId'] = db_id
            if not route_data.get('courierName') and dr.courier:
                route_data['courierName'] = dr.courier.name

    # Inject depot from cached_result_json of existing routes (authoritative source)
    if not result.get('depot'):
        for dr in route_map.values():
            if dr.cached_result_json:
                try:
                    cached = json.loads(dr.cached_result_json)
                    if cached.get('depot'):
                        result['depot'] = cached['depot']
                        break
                except (json.JSONDecodeError, ValueError):
                    logger.warning('Failed to parse cached route JSON for route %s', dr.id)

    return jsonify({'success': True, 'result': result})


@orders_bp.route('/route-generator/distribute/apply', methods=['POST'])
@login_required
def route_generator_distribute_apply():
    data = request.get_json(silent=True) or {}
    result = data.get('result', {})
    selected_date_str = data.get('selected_date', date.today().isoformat())

    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Некоректна дата'}), 400

    routes = result.get('routes', [])
    applied_route_ids = []

    for route_data in routes:
        route_db_id = route_data.get('routeDbId')
        stops = route_data.get('stops', [])

        if route_db_id:
            dr = DeliveryRoute.query.get(route_db_id)
            if not dr:
                continue
            existing_stop_map = {s.delivery_id: s for s in dr.stops}

            for i, stop in enumerate(stops, start=1):
                delivery_id = stop.get('id')
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

                if delivery_id in existing_stop_map:
                    rd = existing_stop_map[delivery_id]
                    rd.stop_order = i
                    rd.duration_from_previous_min = stop.get('driveMin')
                    rd.planned_arrival = planned_arrival
                else:
                    rd = RouteDelivery(
                        route_id=dr.id,
                        delivery_id=delivery_id,
                        stop_order=i,
                        duration_from_previous_min=stop.get('driveMin'),
                        planned_arrival=planned_arrival,
                    )
                    db.session.add(rd)
                    delivery = Delivery.query.get(delivery_id)
                    if delivery and delivery.status == 'Очікує':
                        delivery.status = 'Розподілено'

            dr.deliveries_count = len(stops)
            dr.total_distance_km = route_data.get('totalDistanceKm')
            dr.estimated_duration_min = route_data.get('totalDriveMin')
            dep_str = (route_data.get('departureTime') or '').strip()
            if dep_str:
                try:
                    dr.start_time = datetime.strptime(dep_str, '%H:%M').time()
                except ValueError:
                    logger.warning('Invalid departure time %r, skipping', dep_str)
        else:
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
            )
            db.session.add(dr)
            db.session.flush()

            for i, stop in enumerate(stops, start=1):
                delivery_id = stop.get('id')
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
                    stop_order=i,
                    duration_from_previous_min=stop.get('driveMin'),
                    planned_arrival=planned_arrival,
                )
                db.session.add(rd)
                delivery = Delivery.query.get(delivery_id)
                if delivery and delivery.status == 'Очікує':
                    delivery.status = 'Розподілено'

        applied_route_ids.append(dr.id)

    db.session.commit()
    return jsonify({'success': True, 'applied_count': len(applied_route_ids)})
