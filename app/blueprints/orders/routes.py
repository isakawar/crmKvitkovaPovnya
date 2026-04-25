from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, Response, current_app
from flask_login import login_required
from app.extensions import db
from app.models import Order, Client, Delivery
from app.models.subscription import Subscription
from app.models.delivery_route import RouteDelivery
from app.models.settings import Settings
import logging
import json
import requests
from datetime import date, datetime
from app.services.order_service import (
    SUBSCRIPTION_TYPES,
    create_order_and_deliveries,
    get_or_create_client,
    get_orders,
    paginate_orders,
    update_order,
    delete_order,
)
from app.services.subscription_service import (
    create_subscription,
    extend_subscription as svc_extend_subscription,
    calculate_reschedule_plan,
    apply_reschedule_plan,
)
from app.services.delivery_service import group_deliveries_by_date
from app.services.route_optimizer_service import (
    optimize_json,
    submit_csv_job,
    get_job_status,
    routes_result_to_csv,
    distribute_deliveries,
    RouteOptimizerError,
    RouteOptimizerInfeasibleError,
)
import csv
from sqlalchemy.orm import joinedload

orders_bp = Blueprint('orders', __name__)


@orders_bp.route('/orders', methods=['GET'])
@login_required
def orders_list():
    search_query = (
        request.args.get('q', '').strip()
        or request.args.get('instagram', '').strip()
        or request.args.get('phone', '').strip()
    )
    phone = request.args.get('phone', '').strip()
    instagram = request.args.get('instagram', '').strip()
    city = request.args.get('city', '').strip()
    size = request.args.get('size', '').strip()
    delivery_type_filter = request.args.get('delivery_type', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 100
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    all_orders_count = Order.query.count()
    orders = get_orders(
        q=search_query or None,
        phone=phone or None,
        instagram=instagram or None,
        city=city or None,
        size=size or None,
        delivery_type=delivery_type_filter or None,
        date_from=date_from or None,
        date_to=date_to or None,
    )
    filtered_order_ids = [order.id for order in orders]
    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1
    clients_count = db.session.query(Order.client_id).distinct().count()
    subscription_orders_count = Subscription.query.count()
    subscription_extensions_count = Subscription.query.filter(Subscription.is_extended.is_(True)).count()
    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()
    packaging_types = Settings.query.filter_by(type='packaging_type').order_by(Settings.value).all()
    deliveries = []
    grouped_deliveries = {}
    deliveries_count = 0
    has_next = False
    if filtered_order_ids:
        deliveries_query = (
            Delivery.query
            .options(joinedload(Delivery.order), joinedload(Delivery.client))
            .filter(Delivery.order_id.in_(filtered_order_ids))
            .order_by(
                Delivery.delivery_date.asc(),
                db.case((Delivery.time_from == None, 1), else_=0),
                Delivery.time_from.asc(),
                Delivery.id.asc()
            )
        )
        if date_from:
            try:
                deliveries_query = deliveries_query.filter(
                    Delivery.delivery_date >= datetime.strptime(date_from, '%Y-%m-%d').date()
                )
            except ValueError:
                pass
        else:
            deliveries_query = deliveries_query.filter(
                Delivery.delivery_date >= date.today()
            )
        if date_to:
            try:
                deliveries_query = deliveries_query.filter(
                    Delivery.delivery_date <= datetime.strptime(date_to, '%Y-%m-%d').date()
                )
            except ValueError:
                pass
        deliveries = deliveries_query.all()
        deliveries_count = len(deliveries)
        deliveries = deliveries[start_idx:end_idx]
        grouped_deliveries = group_deliveries_by_date(deliveries)
        has_next = end_idx < deliveries_count

    return render_template(
        'orders/list.html',
        deliveries=deliveries,
        deliveries_count=deliveries_count,
        grouped_deliveries=grouped_deliveries,
        page=page,
        prev_page=prev_page,
        next_page=next_page,
        has_next=has_next,
        orders_count=all_orders_count,
        clients_count=clients_count,
        per_page=per_page,
        cities=cities,
        sizes=sizes,
        for_whom=for_whom,
        subscription_orders_count=subscription_orders_count,
        subscription_extensions_count=subscription_extensions_count,
        delivery_types=delivery_types,
        search_query=search_query,
        city_filter=city,
        size_filter=size,
        delivery_type_filter=delivery_type_filter,
        date_from_filter=date_from,
        date_to_filter=date_to,
        packaging_types=packaging_types,
    )


@orders_bp.route('/orders/new', methods=['GET'])
@login_required
def order_form():
    clients = Client.query.all()
    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()
    return render_template(
        'orders/form.html',
        clients=clients, cities=cities, delivery_types=delivery_types, sizes=sizes, for_whom=for_whom
    )


@orders_bp.route('/orders/new', methods=['POST'])
@login_required
def order_create():
    logging.info('--- ORDER CREATE ---')
    logging.info(f'Form data: {dict(request.form)}')

    is_pickup = request.form.get('is_pickup') == 'on'
    delivery_type = (request.form.get('delivery_type') or '').strip()
    is_subscription = delivery_type in SUBSCRIPTION_TYPES

    order_scenario = (request.form.get('order_scenario') or '').strip()
    if order_scenario == 'subscription':
        is_subscription = True
    elif order_scenario == 'order':
        is_subscription = False

    required_fields = ['recipient_name', 'recipient_phone', 'city', 'size', 'first_delivery_date', 'for_whom']
    if is_subscription:
        required_fields.extend(['delivery_type', 'delivery_day'])
    if not is_pickup:
        required_fields.append('street')

    errors = []
    for field in required_fields:
        value = request.form.get(field)
        if not value or (isinstance(value, str) and value.strip() == ''):
            errors.append(field)

    # Перевіряємо що вказано або client_id або client_instagram
    has_client = (
        (request.form.get('client_id', '').strip().isdigit()) or
        bool(request.form.get('client_instagram', '').strip())
    )
    if not has_client:
        errors.append('client_instagram')

    if errors:
        msg = 'Не всі обовʼязкові поля заповнені: ' + ', '.join(errors)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': msg}), 400
        flash(msg, 'danger')
        return redirect('/orders/new')

    size = request.form.get('size')
    custom_amount = request.form.get('custom_amount')
    if size == 'Власний':
        if not custom_amount or custom_amount.strip() == '':
            error_msg = 'Для власного розміру потрібно вказати суму'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error_msg}), 400
            flash(error_msg, 'danger')
            return redirect('/orders/new')
        try:
            amount = int(custom_amount)
            if amount <= 0:
                error_msg = 'Сума для власного розміру має бути більше 0'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': error_msg}), 400
                flash(error_msg, 'danger')
                return redirect('/orders/new')
        except ValueError:
            error_msg = 'Сума для власного розміру має бути числом'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error_msg}), 400
            flash(error_msg, 'danger')
            return redirect('/orders/new')

    # Certificate check
    certificate_code = (request.form.get('certificate_code') or '').strip().upper()
    certificate = None
    if certificate_code:
        from app.models.certificate import Certificate
        from datetime import date as _date
        certificate = Certificate.query.filter_by(code=certificate_code).first()
        if not certificate:
            error_msg = f'Сертифікат з кодом "{certificate_code}" не знайдено'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error_msg}), 400
            flash(error_msg, 'danger')
            return redirect('/orders/new')
        if certificate.status == 'used':
            error_msg = 'Цей сертифікат вже використано'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error_msg}), 400
            flash(error_msg, 'danger')
            return redirect('/orders/new')
        if certificate.expires_at < _date.today():
            error_msg = 'Термін дії сертифіката закінчився'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error_msg}), 400
            flash(error_msg, 'danger')
            return redirect('/orders/new')

    client_id_raw = request.form.get('client_id', '').strip()
    if client_id_raw and client_id_raw.isdigit():
        client = Client.query.get(int(client_id_raw))
        if not client:
            error_msg = 'Клієнта не знайдено'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error_msg}), 400
            flash(error_msg, 'danger')
            return redirect('/orders/new')
    else:
        client_instagram = request.form['client_instagram']
        client, error = get_or_create_client(client_instagram)
        if error:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error}), 400
            flash(error, 'danger')
            return redirect('/orders/new')

    if is_subscription:
        entity = create_subscription(client, request.form)
        entity_id = entity.orders[0].id if entity.orders else None
        logging.info(f'Subscription created: {entity.id}')

        extend_from_order_id = (request.form.get('extend_from_order_id') or '').strip()
        if extend_from_order_id and extend_from_order_id.isdigit():
            parent_order = Order.query.get(int(extend_from_order_id))
            if parent_order and parent_order.subscription_id:
                parent_sub = Subscription.query.get(parent_order.subscription_id)
                if parent_sub:
                    parent_sub.is_extended = True
                    db.session.commit()

        Subscription.query.filter_by(client_id=client.id, is_renewal_reminder=True).update({'is_renewal_reminder': False})
        db.session.commit()
    else:
        entity = create_order_and_deliveries(client, request.form)
        entity_id = entity.id
        logging.info(f'Order created: {entity_id}')

    if certificate:
        from datetime import datetime as _dt
        certificate.status = 'used'
        certificate.used_at = _dt.utcnow()
        certificate.order_id = entity_id
        db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'order_id': entity_id})
    flash('Замовлення створено!' if not is_subscription else 'Підписку створено!', 'success')
    return redirect('/orders' if not is_subscription else '/subscriptions')


@orders_bp.route('/orders/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
def order_edit(order_id):
    order = Order.query.get_or_404(order_id)
    if request.method == 'POST':
        logging.info(f'EDIT ORDER {order_id}')

        # Capture first active delivery + its date before update
        import datetime as _dt
        active_before = sorted(
            [d for d in order.deliveries if d.status not in ['Доставлено', 'Скасовано']],
            key=lambda d: d.delivery_date or _dt.date.min,
        )
        first_delivery = active_before[0] if active_before else None
        old_date = first_delivery.delivery_date if first_delivery else None

        update_order(order, request.form)

        reschedule_suggestion = None
        new_date_raw = (request.form.get('first_delivery_date') or '').strip()
        if first_delivery and old_date and new_date_raw:
            try:
                new_date = _dt.datetime.strptime(new_date_raw, '%Y-%m-%d').date()
                reschedule_suggestion = calculate_reschedule_plan(first_delivery, old_date, new_date)
            except Exception:
                pass

        return jsonify({'success': True, 'reschedule_suggestion': reschedule_suggestion})

    delivery_comment = next((d.comment for d in order.deliveries if d.comment), None)
    delivery_preferences = next((d.preferences for d in order.deliveries if d.preferences), None)
    delivery_address_comment = next((d.address_comment for d in order.deliveries if d.address_comment), None)
    delivery_bouquet_type = next((d.bouquet_type for d in order.deliveries if d.bouquet_type), None)
    delivery_composition_type = next((d.composition_type for d in order.deliveries if d.composition_type), None)

    return jsonify({
        'id': order.id,
        'client_instagram': order.client.instagram,
        'recipient_name': order.recipient_name,
        'recipient_phone': order.recipient_phone,
        'recipient_social': order.recipient_social,
        'city': order.city,
        'street': order.street,
        'building_number': order.building_number,
        'floor': order.floor,
        'entrance': order.entrance,
        'is_pickup': order.is_pickup,
        'delivery_type': 'One-time',
        'size': order.size,
        'custom_amount': order.custom_amount,
        'first_delivery_date': order.delivery_date.strftime('%Y-%m-%d') if order.delivery_date else '',
        'delivery_day': '',
        'time_from': order.time_from,
        'time_to': order.time_to,
        'comment': order.comment or delivery_comment,
        'preferences': order.preferences or delivery_preferences,
        'for_whom': order.for_whom,
        'delivery_method': order.delivery_method or 'courier',
        'address_comment': order.address_comment or delivery_address_comment,
        'bouquet_type': order.bouquet_type or delivery_bouquet_type,
        'composition_type': order.composition_type or delivery_composition_type,
        'can_extend_subscription': False,
        'additional_phones': [rp.phone for rp in sorted(order.additional_phones, key=lambda x: x.position)],
    })


@orders_bp.route('/orders/<int:order_id>/dependencies', methods=['GET'])
@login_required
def order_dependencies(order_id):
    order = Order.query.get_or_404(order_id)
    from app.models.delivery_route import RouteDelivery, DeliveryRoute
    deliveries = order.deliveries
    routes_info = []
    seen_route_ids = set()
    for d in deliveries:
        for rs in d.route_stops:
            if rs.route_id not in seen_route_ids:
                seen_route_ids.add(rs.route_id)
                route = rs.route
                routes_info.append({
                    'id': route.id,
                    'date': route.route_date.strftime('%d.%m.%Y'),
                    'courier': route.courier.name if route.courier else 'Не призначено',
                    'status': route.status,
                })
    return jsonify({
        'deliveries_count': len(deliveries),
        'routes': routes_info,
    })


@orders_bp.route('/orders/<int:order_id>/delete', methods=['POST'])
@login_required
def order_delete(order_id):
    order = Order.query.get_or_404(order_id)
    delete_order(order)
    return jsonify({'success': True})


@orders_bp.route('/orders/<int:order_id>/bouquet_type', methods=['POST'])
@login_required
def update_order_bouquet_type(order_id):
    order = Order.query.get_or_404(order_id)
    data = request.get_json() or {}
    order.bouquet_type = data.get('bouquet_type') or None
    db.session.commit()
    return jsonify({'success': True})


@orders_bp.route('/orders/deliveries/<int:delivery_id>/dependencies', methods=['GET'])
@login_required
def delivery_dependencies(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    from app.models.delivery_route import DeliveryRoute
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
    from app.models.delivery_route import RouteDelivery
    RouteDelivery.query.filter_by(delivery_id=delivery.id).delete()
    db.session.delete(delivery)
    db.session.flush()
    remaining = Delivery.query.filter_by(order_id=order.id).count()
    if remaining == 0:
        from app.models.recipient_phone import RecipientPhone
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
        def parse_time(value):
            return datetime.strptime(value, '%H:%M').time()
        try:
            parsed_from = parse_time(time_from) if time_from else None
            parsed_to = parse_time(time_to) if time_to else None
        except ValueError:
            return jsonify({'success': False, 'error': 'Невірний формат часу. Використовуйте HH:MM'}), 400

        if parsed_from and parsed_to and parsed_from > parsed_to:
            return jsonify({'success': False, 'error': 'Час "з" має бути меншим за час "до"'}), 400

    delivery_date = None
    if delivery_date_raw:
        try:
            delivery_date = datetime.strptime(delivery_date_raw, '%Y-%m-%d').date()
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
    from app.models.delivery_route import RouteDelivery
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
                date_map[int(item['order_id'])] = datetime.strptime(item['new_date'], '%Y-%m-%d').date()
            except (KeyError, ValueError):
                pass

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


@orders_bp.route('/clients/search', methods=['GET'])
@login_required
def search_clients():
    from sqlalchemy import or_, func
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    query_stripped = query.lstrip('@')
    like_q = f'%{query_stripped}%'
    clients = Client.query.filter(
        or_(
            Client.instagram.ilike(like_q),
            Client.telegram.ilike(like_q),
            Client.phone.contains(query_stripped),
            Client.name.ilike(like_q),
        )
    ).order_by(Client.id.desc()).limit(10).all()

    def display_label(c):
        parts = []
        if c.instagram:
            parts.append(c.instagram)
        if c.telegram:
            tg = c.telegram if c.telegram.startswith('@') else f'@{c.telegram}'
            parts.append(tg)
        if c.phone:
            parts.append(c.phone)
        if c.name:
            parts.append(c.name)
        return ' · '.join(parts) if parts else f'#{c.id}'

    return jsonify([{
        'id': c.id,
        'display': display_label(c),
        'instagram': c.instagram or '',
        'telegram': c.telegram or '',
        'phone': c.phone or '',
        'name': c.name or '',
        'credits': c.credits or 0,
        'personal_discount': c.personal_discount or '',
    } for c in clients])


@orders_bp.route('/orders/last-order', methods=['GET'])
@login_required
def client_last_order():
    from sqlalchemy.orm import joinedload

    client_id = request.args.get('client_id', type=int)
    if not client_id:
        return jsonify({'found': False})

    last_order = (
        Order.query
        .filter_by(client_id=client_id)
        .options(joinedload(Order.subscription))
        .order_by(Order.created_at.desc())
        .first()
    )
    if not last_order:
        return jsonify({'found': False})

    result = {
        'found': True,
        'is_subscription': last_order.subscription_id is not None,
        'recipient_name': last_order.recipient_name or '',
        'recipient_phone': last_order.recipient_phone or '',
        'recipient_social': last_order.recipient_social or '',
        'city': last_order.city or '',
        'street': last_order.street or '',
        'address_comment': last_order.address_comment or '',
        'is_pickup': bool(last_order.is_pickup),
        'delivery_method': last_order.delivery_method or 'courier',
        'size': last_order.size or '',
        'custom_amount': last_order.custom_amount or '',
        'time_from': last_order.time_from or '',
        'time_to': last_order.time_to or '',
        'for_whom': last_order.for_whom or '',
        'preferences': last_order.preferences or '',
        'delivery_type': '',
        'delivery_day': '',
    }
    if last_order.subscription:
        result['delivery_type'] = last_order.subscription.type or ''
        result['delivery_day'] = last_order.subscription.delivery_day or ''

    return jsonify(result)


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
        from app.models.delivery_route import DeliveryRoute
        from app.models.courier import Courier
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
        from app.models.delivery_route import DeliveryRoute as DR
        try:
            vd = datetime.strptime(view_date_str, '%Y-%m-%d').date()
        except ValueError:
            vd = None
        if vd:
            if not selected_date_str:
                selected_date_str = view_date_str
            day_routes = DR.query.filter_by(route_date=vd).order_by(DR.id).all()
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
                            pass
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
        from app.models.courier import Courier
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

    from app.models.delivery_route import DeliveryRoute, RouteDelivery

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
                        pass
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
                    pass
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
                    pass

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


@orders_bp.route('/route-generator/distribute', methods=['GET'])
@login_required
def route_generator_distribute_page():
    date_str = request.args.get('date', date.today().isoformat())
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = date.today()
        date_str = selected_date.isoformat()

    from app.models.delivery_route import DeliveryRoute
    from app.models.courier import Courier

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
    from app.models.delivery_route import DeliveryRoute
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
                    pass

    return jsonify({'success': True, 'result': result})


@orders_bp.route('/route-generator/distribute/apply', methods=['POST'])
@login_required
def route_generator_distribute_apply():
    from app.models.delivery_route import DeliveryRoute

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
                        pass

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
                    pass
        else:
            start_time_val = None
            dep_str = (route_data.get('departureTime') or '').strip()
            if dep_str:
                try:
                    start_time_val = datetime.strptime(dep_str, '%H:%M').time()
                except ValueError:
                    pass
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
                        pass
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


@orders_bp.route('/orders/<int:order_id>/extend-subscription', methods=['POST'])
@login_required
def extend_subscription(order_id):
    """Compatibility shim: find the subscription for this order and extend it."""
    order = Order.query.get_or_404(order_id)
    if not order.subscription_id:
        return jsonify({'success': False, 'error': 'Це не підписка'}), 400

    subscription = Subscription.query.get_or_404(order.subscription_id)
    if subscription.is_extended:
        return jsonify({'success': False, 'error': 'Цю підписку вже продовжено'}), 400

    try:
        svc_extend_subscription(subscription)
        return jsonify({
            'success': True,
            'message': f'Підписку продовжено для клієнта {subscription.client.instagram}',
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f'Помилка продовження підписки: {e}')
        return jsonify({'success': False, 'error': 'Помилка при продовженні підписки'}), 500


@orders_bp.route('/orders/export/csv', methods=['GET'])
@login_required
def export_orders_csv():
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    deliveries_query = (
        Delivery.query
        .options(
            joinedload(Delivery.order).joinedload(Order.client),
            joinedload(Delivery.courier),
        )
        .order_by(Delivery.delivery_date.asc(), Delivery.time_from.asc(), Delivery.id.asc())
    )

    if date_from:
        try:
            deliveries_query = deliveries_query.filter(
                Delivery.delivery_date >= datetime.strptime(date_from, '%Y-%m-%d').date()
            )
        except ValueError:
            pass
    if date_to:
        try:
            deliveries_query = deliveries_query.filter(
                Delivery.delivery_date <= datetime.strptime(date_to, '%Y-%m-%d').date()
            )
        except ValueError:
            pass

    deliveries = deliveries_query.all()

    filename_suffix = ''
    if date_from and date_to:
        filename_suffix = f'_{date_from}_{date_to}'
    elif date_from:
        filename_suffix = f'_{date_from}'

    def generate():
        header = [
            'ID доставки', 'Instagram', 'Отримувач', 'Телефон',
            'Місто', 'Адреса', 'Коментар до адреси',
            'Розмір', 'Дата доставки', 'Час з', 'Час до',
            'Статус', 'Кур\'єр', 'Коментар', 'Побажання', 'Спосіб доставки'
        ]
        yield ','.join('"' + h.replace('"', '""') + '"' for h in header) + '\n'
        for d in deliveries:
            o = d.order
            c = (o.client if o else None)
            row = [
                str(d.id),
                c.instagram if c else '',
                o.recipient_name or '' if o else '',
                d.phone or (o.recipient_phone if o else '') or '',
                o.city or '' if o else '',
                d.street or (o.street if o else '') or '',
                d.address_comment or '',
                d.size or (o.size if o else '') or '',
                d.delivery_date.strftime('%Y-%m-%d') if d.delivery_date else '',
                d.time_from or '',
                d.time_to or '',
                d.status or '',
                d.courier.name if d.courier else '',
                (d.comment or '').replace('\n', ' ').replace('\r', ' '),
                (d.preferences or '').replace('\n', ' ').replace('\r', ' '),
                d.delivery_method or '',
            ]
            yield ','.join('"' + str(x).replace('"', '""') + '"' for x in row) + '\n'

    return Response(generate(), mimetype='text/csv', headers={
        'Content-Disposition': f'attachment; filename=orders_export{filename_suffix}.csv'
    })


@orders_bp.route('/orders/extend-form-from-delivery/<int:delivery_id>')
@login_required
def extend_form_from_delivery(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    order = delivery.order
    client = delivery.client
    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()
    return render_template(
        'orders/extend_modal.html',
        delivery=delivery,
        order=order,
        client=client,
        cities=cities,
        delivery_types=delivery_types,
        sizes=sizes,
        for_whom=for_whom
    )
