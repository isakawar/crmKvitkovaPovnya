from datetime import date, timedelta, datetime
from flask import render_template, request, jsonify
from flask_login import login_required
from sqlalchemy import func, case, and_, or_

from . import dashboard_bp
from app.extensions import db
from app.models import Delivery, Order, Client
from app.models.settings import Settings
from app.models.delivery_route import DeliveryRoute
from app.services.order_service import SUBSCRIPTION_TYPES


@dashboard_bp.route('/dashboard')
@login_required
def dashboard_page():
    today = date.today()
    last_week = today - timedelta(days=7)
    pending_statuses = ['Очікує', 'Розподілено']

    totals_row = db.session.query(
        func.count(Delivery.id),
        func.coalesce(func.sum(case((Delivery.status == 'Доставлено', 1), else_=0)), 0),
        func.coalesce(func.sum(case((and_(Delivery.courier_id.isnot(None), Delivery.status.in_(pending_statuses)), 1), else_=0)), 0),
        func.coalesce(func.sum(case((and_(Delivery.courier_id.is_(None), Delivery.status.in_(pending_statuses)), 1), else_=0)), 0),
    ).filter(
        Delivery.delivery_date == today,
        Delivery.status != 'Скасовано'
    ).first()

    deliveries_last_week = db.session.query(func.count(Delivery.id)).filter(
        Delivery.delivery_date == last_week,
        Delivery.status != 'Скасовано'
    ).scalar() or 0

    deliveries_total = totals_row[0] or 0
    delivered_total = totals_row[1] or 0
    in_couriers_total = totals_row[2] or 0
    unassigned_total = totals_row[3] or 0
    pending_total = in_couriers_total + unassigned_total

    pickup_today = db.session.query(func.count(Delivery.id)).filter(
        Delivery.delivery_date == today,
        Delivery.is_pickup.is_(True),
        Delivery.status != 'Скасовано'
    ).scalar() or 0
    pickup_last_week = db.session.query(func.count(Delivery.id)).filter(
        Delivery.delivery_date == last_week,
        Delivery.is_pickup.is_(True),
        Delivery.status != 'Скасовано'
    ).scalar() or 0

    nova_today = db.session.query(func.count(Delivery.id)).filter(
        Delivery.delivery_date == today,
        Delivery.delivery_method == 'nova_poshta',
        Delivery.status != 'Скасовано'
    ).scalar() or 0
    nova_last_week = db.session.query(func.count(Delivery.id)).filter(
        Delivery.delivery_date == last_week,
        Delivery.delivery_method == 'nova_poshta',
        Delivery.status != 'Скасовано'
    ).scalar() or 0

    courier_today = db.session.query(func.count(Delivery.id)).filter(
        Delivery.delivery_date == today,
        Delivery.is_pickup.is_(False),
        Delivery.delivery_method != 'nova_poshta',
        Delivery.status != 'Скасовано'
    ).scalar() or 0

    new_orders_today = db.session.query(func.count(Order.id)).filter(
        func.date(Order.created_at) == today
    ).scalar() or 0
    new_subscriptions_today = db.session.query(func.count(Order.id)).filter(
        func.date(Order.created_at) == today,
        Order.delivery_type.in_(SUBSCRIPTION_TYPES)
    ).scalar() or 0
    extended_today = db.session.query(func.count(Order.id)).filter(
        Order.subscription_followup_status == 'extended',
        func.date(Order.subscription_followup_at) == today
    ).scalar() or 0
    one_time_today = max(new_orders_today - new_subscriptions_today, 0)

    trend_start = today - timedelta(days=6)
    trend_rows = db.session.query(
        Delivery.delivery_date,
        func.count(Delivery.id)
    ).filter(
        Delivery.delivery_date >= trend_start,
        Delivery.delivery_date <= today,
        Delivery.status != 'Скасовано'
    ).group_by(Delivery.delivery_date).all()
    trend_map = {row[0]: row[1] for row in trend_rows}
    deliveries_trend = []
    for i in range(7):
        day = trend_start + timedelta(days=i)
        deliveries_trend.append({'date': day, 'count': trend_map.get(day, 0)})
    deliveries_trend_max = max([item['count'] for item in deliveries_trend] or [0])

    routes_total = db.session.query(func.count(DeliveryRoute.id)).filter(
        DeliveryRoute.route_date == today
    ).scalar() or 0
    routes_with_courier = db.session.query(func.count(DeliveryRoute.id)).filter(
        DeliveryRoute.route_date == today,
        DeliveryRoute.courier_id.isnot(None)
    ).scalar() or 0
    routes_without_courier = max(routes_total - routes_with_courier, 0)

    last_delivery_subq = (
        db.session.query(
            Delivery.order_id.label('order_id'),
            func.max(Delivery.delivery_date).label('last_delivery_date')
        )
        .filter(Delivery.status != 'Скасовано')
        .group_by(Delivery.order_id)
        .subquery()
    )

    ended_orders = (
        db.session.query(Order, Client, last_delivery_subq.c.last_delivery_date)
        .join(Client, Order.client_id == Client.id)
        .join(last_delivery_subq, last_delivery_subq.c.order_id == Order.id)
        .filter(
            Order.delivery_type.in_(SUBSCRIPTION_TYPES),
            last_delivery_subq.c.last_delivery_date < today,
            Order.is_subscription_extended.is_(False),
            or_(Order.subscription_followup_status.is_(None), Order.subscription_followup_status == 'pending'),
        )
        .order_by(last_delivery_subq.c.last_delivery_date.asc())
        .limit(30)
        .all()
    )

    ended_subscriptions = []
    for order, client, last_date in ended_orders:
        days_overdue = (today - last_date).days if last_date else 0
        ended_subscriptions.append({
            'order_id': order.id,
            'client_instagram': client.instagram,
            'client_phone': client.phone,
            'recipient_name': order.recipient_name,
            'delivery_type': order.delivery_type,
            'size': order.size,
            'last_delivery_date': last_date,
            'days_overdue': days_overdue,
        })

    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()

    return render_template(
        'dashboard/index.html',
        today=today,
        deliveries_total=deliveries_total,
        delivered_total=delivered_total,
        in_couriers_total=in_couriers_total,
        unassigned_total=unassigned_total,
        pending_total=pending_total,
        deliveries_last_week=deliveries_last_week,
        pickup_today=pickup_today,
        pickup_last_week=pickup_last_week,
        nova_today=nova_today,
        nova_last_week=nova_last_week,
        courier_today=courier_today,
        new_orders_today=new_orders_today,
        new_subscriptions_today=new_subscriptions_today,
        extended_today=extended_today,
        one_time_today=one_time_today,
        deliveries_trend=deliveries_trend,
        deliveries_trend_max=deliveries_trend_max,
        routes_total=routes_total,
        routes_with_courier=routes_with_courier,
        routes_without_courier=routes_without_courier,
        ended_subscriptions=ended_subscriptions,
        cities=cities,
        delivery_types=delivery_types,
        sizes=sizes,
        for_whom=for_whom,
    )


@dashboard_bp.route('/dashboard/subscriptions/<int:order_id>/status', methods=['POST'])
@login_required
def update_subscription_followup(order_id):
    payload = request.get_json() or {}
    status = (payload.get('status') or '').strip().lower()
    if status not in ['extended', 'declined']:
        return jsonify({'success': False, 'error': 'Невірний статус'}), 400

    order = Order.query.get_or_404(order_id)
    order.subscription_followup_status = status
    order.subscription_followup_at = datetime.utcnow()
    if status == 'extended':
        order.is_subscription_extended = True

    db.session.commit()
    return jsonify({'success': True})
