import logging
import json
import requests

from flask import render_template, request, redirect, url_for, jsonify, flash, Response, current_app
from flask_login import login_required
from sqlalchemy.orm import joinedload
from datetime import date, datetime

from app.blueprints.orders.routes import orders_bp
from app.extensions import db
from app.models import Delivery
from app.models.delivery_route import DeliveryRoute, RouteDelivery
from app.models.courier import Courier
from app.services.route_optimizer_service import (
    optimize_json,
    submit_csv_job,
    get_job_status,
    routes_result_to_csv,
    RouteOptimizerError,
    RouteOptimizerInfeasibleError,
)

logger = logging.getLogger(__name__)


@orders_bp.route('/route-generator', methods=['GET', 'POST'])
@login_required
def route_generator():
    selected_date_str = request.form.get('delivery_date') if request.method == 'POST' else request.args.get('delivery_date')

    edit_route_id = request.args.get('edit', type=int)
    editing_route = None
    editing_delivery_ids = []
    editing_cached_result = None
    editing_courier = None
    editing_couriers = []
    if edit_route_id:
        editing_route = DeliveryRoute.query.get(edit_route_id)
        if editing_route:
            if not selected_date_str:
                selected_date_str = editing_route.route_date.isoformat()
            editing_delivery_ids = [stop.delivery_id for stop in editing_route.stops]
            if editing_route.cached_result_json:
                editing_cached_result = editing_route.cached_result_json
            editing_courier = editing_route.courier
            editing_couriers = Courier.query.filter_by(active=True).order_by(Courier.name).all()

    view_date_str = request.args.get('view_date')
    view_date_routes_json = None

    if view_date_str and not edit_route_id:
        try:
            vd = datetime.strptime(view_date_str, '%Y-%m-%d').date()
        except ValueError:
            vd = None
        if vd:
            if not selected_date_str:
                selected_date_str = view_date_str
            day_routes = DeliveryRoute.query.filter_by(route_date=vd).order_by(DeliveryRoute.id).all()
            combined_routes = []
            first_cache = None
            for dr in day_routes:
                if not dr.cached_result_json:
                    delivery_ids = [s.delivery_id for s in dr.stops]
                    route_deliveries = Delivery.query.filter(
                        Delivery.id.in_(delivery_ids)
                    ).all() if delivery_ids else []
                    if route_deliveries:
                        try:
                            optimizer_url = current_app.config.get('ROUTE_OPTIMIZER_URL', 'http://localhost:8000')
                            opt_result = optimize_json(deliveries=route_deliveries, optimizer_url=optimizer_url)
                            dr.cached_result_json = json.dumps({
                                **{k: v for k, v in opt_result.items() if k != 'routes'},
                                'routes': opt_result.get('routes', []),
                            })
                            dr.cached_at = datetime.utcnow()
                            db.session.commit()
                        except Exception:
                            logger.exception('Route optimization failed for route %s', dr.id)
                if not dr.cached_result_json:
                    continue
                try:
                    cached = json.loads(dr.cached_result_json)
                except (json.JSONDecodeError, ValueError):
                    continue
                if first_cache is None:
                    first_cache = cached
                for route_entry in cached.get('routes', []):
                    route_entry['routeDbId'] = dr.id
                    if dr.courier:
                        route_entry['courierName'] = dr.courier.name
                    combined_routes.append(route_entry)
            if combined_routes and first_cache:
                view_date_routes_json = json.dumps({
                    'depot': first_cache.get('depot', {}),
                    'routes': combined_routes,
                    'stats': first_cache.get('stats', {}),
                })
        view_date_couriers = Courier.query.filter_by(active=True).order_by(Courier.name).all()
    else:
        view_date_couriers = []

    if not selected_date_str:
        selected_date_str = date.today().isoformat()

    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = date.today()
        selected_date_str = selected_date.isoformat()

    if request.method == 'POST':
        delivery_ids_raw = request.form.getlist('delivery_ids')
        delivery_ids = [int(x) for x in delivery_ids_raw if x.isdigit()]

        post_editing_route_id = request.form.get('editing_route_id', type=int)
        if post_editing_route_id:
            already_routed = (
                db.session.query(RouteDelivery.delivery_id)
                .filter(RouteDelivery.route_id != post_editing_route_id)
                .scalar_subquery()
            )
        else:
            already_routed = db.session.query(RouteDelivery.delivery_id).scalar_subquery()
        base_query = (
            Delivery.query
            .options(joinedload(Delivery.order), joinedload(Delivery.client))
            .filter(
                Delivery.delivery_date == selected_date,
                Delivery.is_pickup == False,
                Delivery.status.in_(['Очікує', 'Розподілено']),
                Delivery.delivery_method != 'nova_poshta',
                ~Delivery.id.in_(already_routed)
            )
            .order_by(Delivery.time_from.asc().nullslast(), Delivery.id.asc())
        )
        deliveries = base_query.filter(Delivery.id.in_(delivery_ids)).all() if delivery_ids else base_query.all()

        if not deliveries:
            return jsonify({'error': 'Немає доставок для оптимізації на вибрану дату.'}), 422

        try:
            optimizer_url = current_app.config.get('ROUTE_OPTIMIZER_URL', 'http://localhost:8000')
            result = optimize_json(deliveries=deliveries, optimizer_url=optimizer_url)
            return jsonify({'result': result, 'selected_date': selected_date_str})
        except RouteOptimizerInfeasibleError as exc:
            return jsonify({'error': str(exc), 'minimum_couriers_required': exc.minimum_couriers_required}), 422
        except RouteOptimizerError as exc:
            return jsonify({'error': str(exc)}), 502

    return render_template(
        'routes/generator.html',
        selected_date=selected_date_str,
        editing_route=editing_route,
        edit_route_id=edit_route_id,
        editing_delivery_ids=editing_delivery_ids,
        editing_cached_result=editing_cached_result,
        editing_courier=editing_courier,
        editing_couriers=editing_couriers,
        view_date_routes=view_date_routes_json,
        view_date=view_date_str,
        view_date_couriers=[{'id': c.id, 'name': c.name} for c in view_date_couriers],
    )


@orders_bp.route('/route-generator/recalculate', methods=['POST'])
@login_required
def route_generator_recalculate():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({'error': 'invalid payload'}), 400

    optimizer_url = current_app.config.get('ROUTE_OPTIMIZER_URL', 'http://localhost:8000')
    url = f"{optimizer_url.rstrip('/')}/api/recalculate"
    headers = {'Content-Type': 'application/json'}
    api_key = current_app.config.get('OPTIMIZER_API_KEY') or ''
    if api_key:
        headers['X-API-Key'] = api_key

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
    except requests.RequestException as exc:
        return jsonify({'error': str(exc)}), 502

    try:
        body = resp.json()
    except ValueError:
        body = {}

    return jsonify(body), resp.status_code


@orders_bp.route('/route-generator/optimize-csv', methods=['POST'])
@login_required
def route_generator_optimize_csv():
    csv_file = request.files.get('file')
    if not csv_file or not csv_file.filename:
        return jsonify({'error': 'Оберіть CSV файл.'}), 422

    optimizer_url = current_app.config.get('ROUTE_OPTIMIZER_URL', 'http://localhost:8000')
    try:
        job_id, result = submit_csv_job(csv_file.stream, csv_file.filename, optimizer_url)
        if result is not None:
            return jsonify({'result': result})
        return jsonify({'job_id': job_id})
    except RouteOptimizerInfeasibleError as exc:
        return jsonify({'error': str(exc), 'minimum_couriers_required': exc.minimum_couriers_required}), 422
    except RouteOptimizerError as exc:
        return jsonify({'error': str(exc)}), 502


@orders_bp.route('/route-generator/job/<job_id>', methods=['GET'])
@login_required
def route_generator_job_status(job_id):
    optimizer_url = current_app.config.get('ROUTE_OPTIMIZER_URL', 'http://localhost:8000')
    try:
        data = get_job_status(job_id, optimizer_url)
        return jsonify(data)
    except RouteOptimizerError as exc:
        return jsonify({'error': str(exc)}), 502


@orders_bp.route('/route-generator/deliveries', methods=['GET'])
@login_required
def route_generator_deliveries():
    date_str = request.args.get('date', date.today().isoformat())
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'invalid date'}), 400

    editing_route_id = request.args.get('editing_route_id', type=int)
    if editing_route_id:
        already_routed = (
            db.session.query(RouteDelivery.delivery_id)
            .filter(RouteDelivery.route_id != editing_route_id)
            .scalar_subquery()
        )
    else:
        already_routed = db.session.query(RouteDelivery.delivery_id).scalar_subquery()

    deliveries = (
        Delivery.query
        .options(joinedload(Delivery.order), joinedload(Delivery.client))
        .filter(
            Delivery.delivery_date == selected_date,
            Delivery.is_pickup == False,
            Delivery.status.in_(['Очікує', 'Розподілено']),
            Delivery.delivery_method != 'nova_poshta',
            db.or_(
                db.and_(Delivery.time_from != None, Delivery.time_from != ''),
                db.and_(Delivery.time_to != None, Delivery.time_to != ''),
            ),
            ~Delivery.id.in_(already_routed)
        )
        .order_by(Delivery.time_from.asc().nullslast(), Delivery.id.asc())
        .all()
    )

    result = []
    for d in deliveries:
        order = d.order
        client = d.client
        result.append({
            'id': d.id,
            'time_from': d.time_from or '',
            'time_to': d.time_to or '',
            'street': d.street or (order.street if order else '') or '',
            'building_number': d.building_number or (order.building_number if order else '') or '',
            'city': order.city if order else '',
            'size': d.size or '',
            'recipient_name': order.recipient_name if order else '',
            'phone': d.phone or '',
            'instagram': client.instagram if client else '',
            'status': d.status or '',
        })

    return jsonify(result)


@orders_bp.route('/route-generator/export-csv', methods=['POST'])
@login_required
def route_generator_export_csv():
    result_json = request.form.get('result_json', '').strip()
    selected_date = request.form.get('selected_date', '').strip()
    if not result_json:
        flash('Немає результату для експорту.', 'warning')
        return redirect(url_for('orders.route_generator', delivery_date=selected_date or date.today().isoformat()))

    try:
        result = json.loads(result_json)
    except json.JSONDecodeError:
        flash('Некоректні дані маршруту для експорту.', 'danger')
        return redirect(url_for('orders.route_generator', delivery_date=selected_date or date.today().isoformat()))

    csv_body = routes_result_to_csv(result)
    filename_date = selected_date or date.today().isoformat()
    return Response(
        csv_body,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=optimized_routes_{filename_date}.csv'}
    )
