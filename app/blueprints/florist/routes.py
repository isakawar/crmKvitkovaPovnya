from decimal import Decimal
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models.delivery_route import DeliveryRoute, RouteDelivery
from app.models.delivery import Delivery
from app.extensions import db
from sqlalchemy.orm import joinedload
from sqlalchemy import func
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
        .order_by(DeliveryRoute.start_time.asc().nullslast())
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
    unrouted_all = [d for d in courier_deliveries if d.id not in route_delivery_ids]
    taxi_deliveries = [d for d in unrouted_all if d.courier and d.courier.is_taxi]
    unrouted_courier_deliveries = [d for d in unrouted_all if not (d.courier and d.courier.is_taxi)]
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
        taxi_deliveries=taxi_deliveries,
        nova_poshta_deliveries=nova_poshta_deliveries,
        pickup_deliveries=pickup_deliveries,
        florist_status_options=FLORIST_STATUS_OPTIONS,
        subscription_delivery_index=subscription_delivery_index,
    )


def _parse_month(month_raw):
    today = datetime.utcnow()
    default = datetime(today.year, today.month, 1)
    if not month_raw:
        return default
    try:
        parsed = datetime.strptime(month_raw, '%Y-%m')
        return datetime(parsed.year, parsed.month, 1)
    except ValueError:
        return default


def _month_bounds(month_start):
    if month_start.month == 12:
        month_end = datetime(month_start.year + 1, 1, 1)
    else:
        month_end = datetime(month_start.year, month_start.month + 1, 1)
    return month_start, month_end


def _adjacent_months(month_start):
    # previous month
    if month_start.month == 1:
        prev = datetime(month_start.year - 1, 12, 1)
    else:
        prev = datetime(month_start.year, month_start.month - 1, 1)
    # next month — only expose if not in the future
    if month_start.month == 12:
        nxt = datetime(month_start.year + 1, 1, 1)
    else:
        nxt = datetime(month_start.year, month_start.month + 1, 1)
    return prev, nxt


MONTH_NAMES_UK = {
    1: 'Січень', 2: 'Лютий', 3: 'Березень', 4: 'Квітень',
    5: 'Травень', 6: 'Червень', 7: 'Липень', 8: 'Серпень',
    9: 'Вересень', 10: 'Жовтень', 11: 'Листопад', 12: 'Грудень',
}


@florist_bp.route('/florist/sales', methods=['GET'])
@login_required
def florist_sales():
    from app.models.florist_sale import FloristSale

    month_raw = (request.args.get('month') or '').strip()
    month_start = _parse_month(month_raw)
    month_start, month_end = _month_bounds(month_start)

    now_utc = datetime.utcnow()
    current_month_start = datetime(now_utc.year, now_utc.month, 1)
    is_current_month = (month_start == current_month_start)

    prev_month, next_month = _adjacent_months(month_start)
    has_next = next_month <= current_month_start  # don't navigate into future

    stats = (
        db.session.query(
            func.count(FloristSale.id),
            func.sum(FloristSale.amount),
            func.avg(FloristSale.amount),
            func.sum(FloristSale.bonus_amount),
        )
        .filter(
            FloristSale.florist_id == current_user.id,
            FloristSale.created_at >= month_start,
            FloristSale.created_at < month_end,
        )
        .one()
    )
    count = stats[0] or 0
    total_amount = float(stats[1] or 0)
    avg_amount = float(stats[2] or 0)
    total_bonus = float(stats[3] or 0)

    page = request.args.get('page', 1, type=int)
    per_page = 15
    pagination = (
        FloristSale.query
        .filter(
            FloristSale.florist_id == current_user.id,
            FloristSale.created_at >= month_start,
            FloristSale.created_at < month_end,
        )
        .order_by(FloristSale.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    selected_month_str = month_start.strftime('%Y-%m')
    selected_month_label = f"{MONTH_NAMES_UK[month_start.month]} {month_start.year}"

    return render_template(
        'florist/sales.html',
        count=count,
        total_amount=total_amount,
        avg_amount=avg_amount,
        total_bonus=total_bonus,
        pagination=pagination,
        sales=pagination.items,
        now_utc=now_utc,
        is_current_month=is_current_month,
        selected_month=selected_month_str,
        selected_month_label=selected_month_label,
        prev_month=prev_month.strftime('%Y-%m'),
        next_month=next_month.strftime('%Y-%m') if has_next else None,
    )


@florist_bp.route('/florist/sales', methods=['POST'])
@login_required
def florist_sales_add():
    from app.models.florist_sale import FloristSale
    from app.models.transaction import Transaction

    data = request.get_json(silent=True) or {}
    try:
        amount = Decimal(str(data.get('amount', 0)))
    except Exception:
        return jsonify({'success': False, 'error': 'Некоректна сума'}), 400

    if amount <= 0:
        return jsonify({'success': False, 'error': 'Сума має бути більше нуля'}), 400

    payment_type = data.get('payment_type', 'cash')
    if payment_type not in ('monobank', 'cash'):
        payment_type = 'cash'

    comment = (data.get('comment') or '').strip() or None
    bonus_percent = Decimal('5.0')
    bonus_amount = (amount * bonus_percent / Decimal('100')).quantize(Decimal('0.01'))

    sale = FloristSale(
        florist_id=current_user.id,
        created_by=current_user.id,
        amount=amount,
        bonus_percent=bonus_percent,
        bonus_amount=bonus_amount,
        payment_type=payment_type,
        comment=comment,
    )
    db.session.add(sale)
    db.session.flush()

    txn = Transaction(
        transaction_type='credit',
        client_id=None,
        amount=int(amount),
        payment_type=payment_type,
        comment='Офлайн продаж',
        date=date.today(),
    )
    db.session.add(txn)
    db.session.flush()
    sale.transaction_id = txn.id

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

    return jsonify({'success': True, 'id': sale.id})


@florist_bp.route('/florist/sales/<int:sale_id>/edit', methods=['POST'])
@login_required
def florist_sales_edit(sale_id):
    from app.models.florist_sale import FloristSale
    from app.models.transaction import Transaction

    sale = FloristSale.query.filter_by(id=sale_id, florist_id=current_user.id).first()
    if not sale:
        return jsonify({'success': False, 'error': 'Продаж не знайдено'}), 404

    if (datetime.utcnow() - sale.created_at).total_seconds() > 86400:
        return jsonify({'success': False, 'error': 'Редагування заборонено після 24 годин'}), 403

    data = request.get_json(silent=True) or {}
    try:
        amount = Decimal(str(data.get('amount', 0)))
    except Exception:
        return jsonify({'success': False, 'error': 'Некоректна сума'}), 400

    if amount <= 0:
        return jsonify({'success': False, 'error': 'Сума має бути більше нуля'}), 400

    payment_type = data.get('payment_type', sale.payment_type or 'cash')
    if payment_type not in ('monobank', 'cash'):
        payment_type = 'cash'

    comment = (data.get('comment') or '').strip() or None
    sale.amount = amount
    sale.bonus_amount = (amount * sale.bonus_percent / Decimal('100')).quantize(Decimal('0.01'))
    sale.payment_type = payment_type
    sale.comment = comment

    if sale.transaction_id:
        txn = Transaction.query.get(sale.transaction_id)
        if txn:
            txn.amount = int(amount)
            txn.payment_type = payment_type

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

    return jsonify({'success': True})
