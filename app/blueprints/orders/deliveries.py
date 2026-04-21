"""Delivery mutation endpoints: delete, time updates, and reschedule."""
import logging

from flask import request, jsonify
from flask_login import login_required

from app.blueprints.orders import orders_bp
from app.blueprints.orders._helpers import parse_ymd, parse_hm
from app.extensions import db
from app.models import Order, Delivery
from app.models.delivery_route import RouteDelivery, DeliveryRoute
from app.models.recipient_phone import RecipientPhone
from app.services.subscription_service import calculate_reschedule_plan, apply_reschedule_plan

logger = logging.getLogger(__name__)


@orders_bp.route('/orders/deliveries/<int:delivery_id>/dependencies', methods=['GET'])
@login_required
def delivery_dependencies(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    routes_info = []
    seen_route_ids = set()
    for rs in delivery.route_stops:
        if rs.route_id not in seen_route_ids:
            seen_route_ids.add(rs.route_id)
            route = rs.route
            routes_info.append({
                'id': route.id,
                'date': route.route_date.strftime('%d.%m.%Y'),
                'courier': route.courier.name if route.courier else 'Не призначено',
                'status': route.status,
            })
    return jsonify({'deliveries_count': 1, 'routes': routes_info})


@orders_bp.route('/orders/deliveries/<int:delivery_id>/delete', methods=['POST'])
@login_required
def delivery_delete(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    order = delivery.order
    RouteDelivery.query.filter_by(delivery_id=delivery.id).delete()
    db.session.delete(delivery)
    db.session.flush()
    remaining = Delivery.query.filter_by(order_id=order.id).count()
    if remaining == 0:
        RecipientPhone.query.filter_by(order_id=order.id).delete()
        db.session.delete(order)
    db.session.commit()
    return jsonify({'success': True})


@orders_bp.route('/orders/deliveries/time', methods=['POST'])
@login_required
def update_delivery_times():
    data = request.get_json() or {}
    delivery_ids = data.get('delivery_ids') or []
    time_from = (data.get('time_from') or '').strip()
    time_to = (data.get('time_to') or '').strip()
    clear_time = bool(data.get('clear'))
    delivery_date_raw = (data.get('delivery_date') or '').strip()

    if not isinstance(delivery_ids, list) or not delivery_ids:
        return jsonify({'success': False, 'error': 'Оберіть доставки для оновлення'}), 400
    if not time_from and not time_to and not clear_time and not delivery_date_raw:
        return jsonify({'success': False, 'error': 'Вкажіть час доставки'}), 400

    if time_from != '∞':
        try:
            parsed_from = parse_hm(time_from) if time_from else None
            parsed_to = parse_hm(time_to) if time_to else None
        except ValueError:
            return jsonify({'success': False, 'error': 'Невірний формат часу. Використовуйте HH:MM'}), 400

        if parsed_from and parsed_to and parsed_from > parsed_to:
            return jsonify({'success': False, 'error': 'Час "з" має бути меншим за час "до"'}), 400

    delivery_date = None
    if delivery_date_raw:
        try:
            delivery_date = parse_ymd(delivery_date_raw)
        except ValueError:
            return jsonify({'success': False, 'error': 'Невірний формат дати. Використовуйте YYYY-MM-DD'}), 400

    deliveries = Delivery.query.filter(Delivery.id.in_(delivery_ids)).all()
    if not deliveries:
        return jsonify({'success': False, 'error': 'Доставки не знайдені'}), 404

    old_dates = {}
    for delivery in deliveries:
        old_dates[delivery.id] = delivery.delivery_date
        delivery.time_from = None if clear_time else (time_from or None)
        delivery.time_to = None if clear_time else (time_to or None)
        if delivery_date:
            delivery.delivery_date = delivery_date
            if delivery.status == 'Розподілено':
                RouteDelivery.query.filter_by(delivery_id=delivery.id).delete()
                delivery.status = 'Очікує'
    db.session.commit()

    reschedule_suggestion = None
    if delivery_date and len(deliveries) == 1:
        d = deliveries[0]
        reschedule_suggestion = calculate_reschedule_plan(d, old_dates[d.id], delivery_date)

    return jsonify({
        'success': True,
        'updated': len(deliveries),
        'reschedule_suggestion': reschedule_suggestion,
    })


@orders_bp.route('/orders/deliveries/reschedule-subsequent', methods=['POST'])
@login_required
def reschedule_subsequent_deliveries():
    data = request.get_json() or {}
    delivery_id = data.get('delivery_id')
    custom_dates = data.get('dates')  # [{order_id, new_date: 'YYYY-MM-DD'}, ...]

    if not delivery_id:
        return jsonify({'success': False, 'error': 'Вкажіть delivery_id'}), 400

    delivery = Delivery.query.get(delivery_id)
    if not delivery:
        return jsonify({'success': False, 'error': 'Доставку не знайдено'}), 404

    order = delivery.order
    if not order or not order.subscription_id or order.sequence_number is None:
        return jsonify({'success': False, 'error': 'Доставка не належить до підписки'}), 400

    if order.subscription.type == 'Monthly':
        return jsonify({'success': False, 'error': 'Місячні підписки не підтримуються'}), 400

    if custom_dates:
        # Apply user-edited dates explicitly
        date_map = {}
        for item in custom_dates:
            try:
                date_map[int(item['order_id'])] = parse_ymd(item['new_date'])
            except (KeyError, ValueError):
                logger.warning('Skipping invalid custom_date entry: %r', item)

        count = 0
        for order_id, new_date in date_map.items():
            target_order = Order.query.get(order_id)
            if not target_order:
                continue
            for d in target_order.deliveries:
                if d.status not in ('Доставлено', 'Скасовано'):
                    d.delivery_date = new_date
                    if d.status == 'Розподілено':
                        RouteDelivery.query.filter_by(delivery_id=d.id).delete()
                        d.status = 'Очікує'
                    count += 1
        db.session.commit()
        return jsonify({'success': True, 'rescheduled': count})

    count = apply_reschedule_plan(delivery)
    return jsonify({'success': True, 'rescheduled': count})
