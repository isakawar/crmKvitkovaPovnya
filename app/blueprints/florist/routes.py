from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app.models.delivery_route import DeliveryRoute, RouteDelivery
from app.models.delivery import Delivery
from app.extensions import db
from sqlalchemy.orm import joinedload
from datetime import date, datetime, timedelta

florist_bp = Blueprint('florist', __name__)

WEEKDAY_MAP = {
    0: 'Понеділок',
    1: 'Вівторок',
    2: 'Середа',
    3: 'Четвер',
    4: "П'ятниця",
    5: 'Субота',
    6: 'Неділя',
}

FLORIST_STATUS_ASSEMBLED = 'Зібрано'
FLORIST_STATUS_HANDOFF = "Передано кур'єру"
FLORIST_STATUS_DELIVERED = 'Доставлено'
FLORIST_STATUS_OPTIONS = {
    'assembled': FLORIST_STATUS_ASSEMBLED,
    'handoff': FLORIST_STATUS_HANDOFF,
    'delivered': FLORIST_STATUS_DELIVERED,
}


def _parse_selected_date(raw_value, fallback_date):
    if not raw_value:
        return fallback_date
    try:
        return datetime.strptime(raw_value, '%Y-%m-%d').date()
    except ValueError:
        return fallback_date


def _build_subscription_delivery_index(order_ids):
    """Return {delivery_id: sequence_number} from Order.sequence_number."""
    if not order_ids:
        return {}

    from app.models.order import Order as _Order
    rows = (
        db.session.query(Delivery.id, _Order.sequence_number)
        .join(_Order, _Order.id == Delivery.order_id)
        .filter(
            Delivery.order_id.in_(order_ids),
            _Order.sequence_number.isnot(None),
            Delivery.status != 'Скасовано',
        )
        .all()
    )

    return {delivery_id: seq for delivery_id, seq in rows}


@florist_bp.route('/florist/deliveries/status', methods=['POST'])
@login_required
def florist_bulk_update_status():
    payload = request.get_json(silent=True) or {}
    delivery_ids_raw = payload.get('delivery_ids') or []
    status_key = (payload.get('status_key') or '').strip()
    florist_status = FLORIST_STATUS_OPTIONS.get(status_key)

    if not florist_status:
        return jsonify({'success': False, 'error': 'Некоректний статус'}), 400

    normalized_ids = []
    for value in delivery_ids_raw:
        try:
            normalized_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    normalized_ids = list(set(normalized_ids))
    if not normalized_ids:
        return jsonify({'success': False, 'error': 'Не обрано доставки'}), 400

    deliveries = Delivery.query.filter(Delivery.id.in_(normalized_ids)).all()
    if not deliveries:
        return jsonify({'success': False, 'error': 'Доставки не знайдено'}), 404

    now_utc = datetime.utcnow()
    updated_count = 0
    for delivery in deliveries:
        if delivery.status == 'Скасовано':
            continue

        delivery.florist_status = florist_status
        updated_count += 1

        if status_key == 'handoff' and delivery.status != 'Доставлено':
            delivery.status = 'Розподілено'
            delivery.status_changed_at = now_utc

        if status_key == 'delivered':
            delivery.status = 'Доставлено'
            delivery.status_changed_at = now_utc
            if not delivery.delivered_at:
                delivery.delivered_at = now_utc

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': True, 'updated_count': updated_count})


@florist_bp.route('/florist')
@login_required
def florist_routes():
    today = date.today()
    selected_date = _parse_selected_date(request.args.get('date', '').strip(), today)

    routes = (
        DeliveryRoute.query
        .options(
            joinedload(DeliveryRoute.courier),
            joinedload(DeliveryRoute.stops)
            .joinedload(RouteDelivery.delivery)
            .joinedload(Delivery.order),
            joinedload(DeliveryRoute.stops)
            .joinedload(RouteDelivery.delivery)
            .joinedload(Delivery.client),
        )
        .filter(
            DeliveryRoute.route_date == selected_date,
            DeliveryRoute.status != 'rejected'
        )
        .order_by(DeliveryRoute.id)
        .all()
    )

    route_delivery_ids = {
        stop.delivery_id
        for route in routes
        for stop in route.stops
        if stop.delivery_id
    }

    all_deliveries = (
        Delivery.query
        .options(
            joinedload(Delivery.order),
            joinedload(Delivery.client),
            joinedload(Delivery.courier),
        )
        .filter(
            Delivery.delivery_date == selected_date,
            Delivery.status != 'Скасовано'
        )
        .order_by(Delivery.time_from.asc().nullslast(), Delivery.id.asc())
        .all()
    )

    routed_deliveries_count = len(route_delivery_ids)
    delivered_count = sum(1 for d in all_deliveries if d.status == 'Доставлено')

    courier_deliveries = [
        d for d in all_deliveries
        if not d.is_pickup and d.delivery_method != 'nova_poshta'
    ]
    unrouted_courier_deliveries = [d for d in courier_deliveries if d.id not in route_delivery_ids]
    nova_poshta_deliveries = [d for d in all_deliveries if d.delivery_method == 'nova_poshta']
    pickup_deliveries = [d for d in all_deliveries if d.is_pickup]
    order_ids = {delivery.order_id for delivery in all_deliveries if delivery.order_id}
    subscription_delivery_index = _build_subscription_delivery_index(order_ids)

    return render_template(
        'florist/list.html',
        weekday_map=WEEKDAY_MAP,
        routes=routes,
        today=today,
        selected_date=selected_date,
        timedelta=timedelta,
        total_deliveries=len(all_deliveries),
        delivered_count=delivered_count,
        pending_count=max(len(all_deliveries) - delivered_count, 0),
        routes_count=len(routes),
        routed_deliveries_count=routed_deliveries_count,
        unrouted_courier_deliveries=unrouted_courier_deliveries,
        nova_poshta_deliveries=nova_poshta_deliveries,
        pickup_deliveries=pickup_deliveries,
        florist_status_options=FLORIST_STATUS_OPTIONS,
        subscription_delivery_index=subscription_delivery_index,
    )
