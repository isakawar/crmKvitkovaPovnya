"""Order CRUD, client search, CSV export, and subscription extension endpoints."""
import logging

from flask import render_template, request, redirect, url_for, jsonify, flash, Response
from flask_login import login_required
from sqlalchemy.orm import joinedload
from sqlalchemy import or_
from datetime import date

from app.blueprints.orders import orders_bp
from app.blueprints.orders._helpers import parse_ymd
from app.extensions import db
from app.models import Order, Client, Delivery
from app.models.certificate import Certificate
from app.models.subscription import Subscription
from app.models.settings import Settings
from app.models.delivery_route import RouteDelivery, DeliveryRoute
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
)
from app.services.delivery_service import group_deliveries_by_date

logger = logging.getLogger(__name__)


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
                    Delivery.delivery_date >= parse_ymd(date_from)
                )
            except ValueError:
                logger.warning('Invalid date_from %r, skipping filter', date_from)
        else:
            deliveries_query = deliveries_query.filter(
                Delivery.delivery_date >= date.today()
            )
        if date_to:
            try:
                deliveries_query = deliveries_query.filter(
                    Delivery.delivery_date <= parse_ymd(date_to)
                )
            except ValueError:
                logger.warning('Invalid date_to %r, skipping filter', date_to)
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
    logger.info('--- ORDER CREATE ---')
    logger.info('Form data: %s', dict(request.form))

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
        logger.info('Subscription created: %s', entity.id)
    else:
        entity = create_order_and_deliveries(client, request.form)
        entity_id = entity.id
        logger.info('Order created: %s', entity_id)

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
        logger.info('EDIT ORDER %s', order_id)

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
                new_date = parse_ymd(new_date_raw)
                reschedule_suggestion = calculate_reschedule_plan(first_delivery, old_date, new_date)
            except Exception:
                logger.exception('Failed to calculate reschedule plan for date %r', new_date_raw)

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


@orders_bp.route('/clients/search', methods=['GET'])
@login_required
def search_clients():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    like_q = f'%{query}%'
    clients = Client.query.filter(
        or_(
            Client.instagram.ilike(like_q),
            Client.telegram.ilike(like_q),
            Client.phone.contains(query),
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
        logger.exception('Помилка продовження підписки: %s', e)
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
                Delivery.delivery_date >= parse_ymd(date_from)
            )
        except ValueError:
            logger.warning('Invalid date_from %r, skipping filter', date_from)
    if date_to:
        try:
            deliveries_query = deliveries_query.filter(
                Delivery.delivery_date <= parse_ymd(date_to)
            )
        except ValueError:
            logger.warning('Invalid date_to %r, skipping filter', date_to)

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
