from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, Response, current_app
from flask_login import login_required
from app.extensions import db
from app.models import Order, Client, Delivery
from app.models.delivery_route import RouteDelivery
from app.models.settings import Settings
import logging
import json
import requests
from datetime import date, datetime
from app.services.order_service import get_orders, paginate_orders, update_order, delete_order, get_or_create_client, create_order_and_deliveries
from app.services.route_optimizer_service import (
    optimize_json,
    submit_csv_job,
    get_job_status,
    routes_result_to_csv,
    RouteOptimizerError,
    RouteOptimizerInfeasibleError,
)
import csv
from sqlalchemy.orm import joinedload

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/orders', methods=['GET'])
@login_required
def orders_list():
    phone = request.args.get('phone', '').strip()
    instagram = request.args.get('instagram', '').strip()
    city = request.args.get('city', '').strip()
    delivery_type = request.args.get('delivery_type', '').strip()
    size = request.args.get('size', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 30
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    all_orders_count = Order.query.count()
    orders = get_orders(phone, instagram, city if city else None, delivery_type if delivery_type else None, size if size else None)
    orders_on_page, has_next = paginate_orders(orders, page, per_page)
    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1
    clients_count = db.session.query(Order.client_id).distinct().count()
    subscription_extensions_count = Order.query.filter_by(is_subscription_extended=True).count()
    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()
    return render_template('orders_list.html', orders_on_page=orders_on_page, page=page, prev_page=prev_page, next_page=next_page, has_next=has_next, orders_count=all_orders_count, clients_count=clients_count, per_page=per_page, cities=cities, delivery_types=delivery_types, sizes=sizes, for_whom=for_whom, subscription_extensions_count=subscription_extensions_count)

@orders_bp.route('/orders/new', methods=['GET'])
@login_required
def order_form():
    clients = Client.query.all()
    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()
    return render_template('order_form.html', clients=clients, cities=cities, delivery_types=delivery_types, sizes=sizes, for_whom=for_whom)

@orders_bp.route('/orders/new', methods=['POST'])
@login_required
def order_create():
    logging.info('--- ORDER CREATE ---')
    logging.info(f'Form data: {dict(request.form)}')
    
    is_pickup = request.form.get('is_pickup') == 'on'
    required_fields = ['client_instagram', 'recipient_name', 'recipient_phone', 'city', 'delivery_type', 'size', 'first_delivery_date', 'delivery_day', 'for_whom']
    if not is_pickup:
        required_fields.append('street')
    errors = []
    for field in required_fields:
        value = request.form.get(field)
        if not value or (isinstance(value, str) and value.strip() == ''):
            errors.append(field)
    
    if errors:
        msg = 'Не всі обовʼязкові поля заповнені: ' + ', '.join(errors)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': msg}), 400
        flash(msg, 'danger')
        return redirect('/orders/new')
    
    # Валідація custom_amount для власного розміру
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
    
    # Отримуємо клієнта
    client_instagram = request.form['client_instagram']
    client, error = get_or_create_client(client_instagram)
    if error:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': error}), 400
        flash(error, 'danger')
        return redirect('/orders/new')
    
    # Створюємо замовлення
    order = create_order_and_deliveries(client, request.form)
    logging.info(f'Order created: {order.id}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'order_id': order.id})
    flash('Замовлення створено, доставки додано!', 'success')
    return redirect('/orders')

@orders_bp.route('/orders/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
def order_edit(order_id):
    order = Order.query.get_or_404(order_id)
    if request.method == 'POST':
        logging.info(f'EDIT ORDER {order_id}')
        logging.info(f'Before update: order.id={order.id}, form={dict(request.form)}')
        update_order(order, request.form)
        logging.info(f'After update: order.id={order.id}')
        return jsonify({'success': True})
    # --- Перевірка, чи можна продовжити підписку ---
    can_extend_subscription = True
    if order.delivery_type in ['Weekly', 'Monthly', 'Bi-weekly']:
        if getattr(order, 'is_subscription_extended', False):
            can_extend_subscription = False
        else:
            can_extend_subscription = True
    else:
        can_extend_subscription = False
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
        'delivery_type': order.delivery_type,
        'size': order.size,
        'custom_amount': order.custom_amount,
        'first_delivery_date': order.first_delivery_date.strftime('%Y-%m-%d'),
        'delivery_day': order.delivery_day,
        'time_from': order.time_from,
        'time_to': order.time_to,
        'comment': order.comment,
        'preferences': order.preferences,
        'for_whom': order.for_whom,
        'delivery_method': order.delivery_method or 'courier',
        'can_extend_subscription': can_extend_subscription
    })

@orders_bp.route('/orders/<int:order_id>/delete', methods=['POST'])
@login_required
def order_delete(order_id):
    order = Order.query.get_or_404(order_id)
    delete_order(order)
    return jsonify({'success': True})

@orders_bp.route('/clients/search', methods=['GET'])
@login_required
def search_clients():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    
    clients = Client.query.filter(Client.instagram.contains(query)).limit(10).all()
    return jsonify([{'instagram': c.instagram} for c in clients])

@orders_bp.route('/route-generator', methods=['GET', 'POST'])
@login_required
def route_generator():
    selected_date_str = request.form.get('delivery_date') if request.method == 'POST' else request.args.get('delivery_date')
    if not selected_date_str:
        selected_date_str = date.today().isoformat()

    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = date.today()
        selected_date_str = selected_date.isoformat()

    optimizer_result = None
    result_json = ''
    deliveries = []
    infeasible_error = None
    general_error = None

    if request.method == 'POST':
        # AJAX — submit job, return job_id
        delivery_ids_raw = request.form.getlist('delivery_ids')
        delivery_ids = [int(x) for x in delivery_ids_raw if x.isdigit()]

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
        'route_generator.html',
        selected_date=selected_date_str,
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
            # Sync mode — result ready immediately
            return jsonify({'result': result})
        # Async mode — poll job
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

    already_routed = db.session.query(RouteDelivery.delivery_id).scalar_subquery()

    deliveries = (
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
            'size': d.bouquet_size or d.size or '',
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
    if not routes:
        return jsonify({'error': 'Немає маршрутів для збереження'}), 400

    from app.models.delivery_route import DeliveryRoute, RouteDelivery

    # Build address → delivery_id map (optimizer doesn't echo IDs back in stops)
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

    saved_route_ids = []
    for route_data in routes:
        stops = route_data.get('stops', [])
        if not stops:
            continue

        dr = DeliveryRoute(
            route_date=selected_date,
            status='draft',
            deliveries_count=len(stops),
            total_distance_km=route_data.get('totalDistanceKm'),
            estimated_duration_min=route_data.get('totalDriveMin'),
        )
        db.session.add(dr)
        db.session.flush()

        for i, stop in enumerate(stops):
            # Try direct id first, fall back to address matching
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

    db.session.commit()
    return jsonify({'success': True, 'route_ids': saved_route_ids, 'count': len(saved_route_ids)})


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

@orders_bp.route('/orders/<int:order_id>/extend-subscription', methods=['POST'])
@login_required
def extend_subscription(order_id):
    """Продовжити підписку для замовлення"""
    order = Order.query.get_or_404(order_id)
    
    # Перевіряємо, чи це підписка
    if order.delivery_type not in ['Weekly', 'Monthly', 'Bi-weekly']:
        return jsonify({'success': False, 'error': 'Це не підписка'}), 400
    
    # Знаходимо доставку з is_subscription=False (5-та доставка)
    unpaid_delivery = Delivery.query.filter_by(
        order_id=order_id, 
        is_subscription=False
    ).first()
    
    if not unpaid_delivery:
        return jsonify({'success': False, 'error': 'Не знайдено неоплачену доставку'}), 404
    
    try:
        # --- КЛОНУЄМО ORDER ---
        new_order = Order(
            client_id=order.client_id,
            recipient_name=order.recipient_name,
            recipient_phone=order.recipient_phone,
            recipient_social=order.recipient_social,
            city=order.city,
            street=order.street,
            building_number=order.building_number,
            floor=order.floor,
            entrance=order.entrance,
            is_pickup=order.is_pickup,
            delivery_type=order.delivery_type,
            size=order.size,
            custom_amount=order.custom_amount,
            first_delivery_date=order.first_delivery_date,
            delivery_day=order.delivery_day,
            time_from=order.time_from,
            time_to=order.time_to,
            comment=order.comment,
            preferences=order.preferences,
            for_whom=order.for_whom,
            bouquet_size=order.bouquet_size,
            price_at_order=order.price_at_order,
            periodicity=order.periodicity,
            preferred_days=order.preferred_days
        )
        db.session.add(new_order)
        db.session.flush()  # Щоб отримати new_order.id

        # --- ПРИВʼЯЗУЄМО ДОСТАВКИ ДО НОВОГО ORDER ---
        unpaid_delivery.status = 'Очікує'
        unpaid_delivery.is_subscription = True
        unpaid_delivery.order_id = new_order.id
        # Відмічаємо старий order як продовжений
        order.is_subscription_extended = True
        
        # Створюємо 4 нові доставки
        from app.services.order_service import WEEKDAY_MAP
        import datetime
        import calendar
        
        last_delivery = Delivery.query.filter_by(order_id=order_id).order_by(Delivery.delivery_date.desc()).first()
        if not last_delivery:
            return jsonify({'success': False, 'error': 'Не знайдено доставки замовлення'}), 404
        
        prev_date = last_delivery.delivery_date
        desired_weekday = WEEKDAY_MAP.get(order.delivery_day, 0)
        deliveries = []
        
        for i in range(4):
            if order.delivery_type == 'Weekly':
                next_date = prev_date + datetime.timedelta(days=1)
                while next_date.weekday() != desired_weekday:
                    next_date += datetime.timedelta(days=1)
            elif order.delivery_type == 'Bi-weekly':
                next_date = prev_date + datetime.timedelta(days=8)
                while next_date.weekday() != desired_weekday:
                    next_date += datetime.timedelta(days=1)
            elif order.delivery_type == 'Monthly':
                year = prev_date.year + (prev_date.month // 12)
                month = (prev_date.month % 12) + 1
                c = calendar.Calendar()
                month_days = [d for d in c.itermonthdates(year, month) if d.month == month and d.weekday() == desired_weekday]
                next_date = None
                for d in month_days:
                    if d > prev_date:
                        next_date = d
                        break
                if not next_date:
                    next_date = prev_date + datetime.timedelta(days=30)
            else:
                next_date = prev_date + datetime.timedelta(weeks=1)
            deliveries.append(next_date)
            prev_date = next_date
        
        for i, d_date in enumerate(deliveries):
            is_subscription = i < 3
            status = 'Очікує' if is_subscription else 'Не оплачена'
            delivery = Delivery(
                order_id=new_order.id,
                client_id=order.client_id,
                delivery_date=d_date,
                status=status,
                comment=order.comment if i == 0 else '',
                street=order.street if not order.is_pickup else None,
                building_number=order.building_number if not order.is_pickup else None,
                time_from=order.time_from,
                time_to=order.time_to,
                size=order.size,
                phone=order.recipient_phone,
                is_pickup=order.is_pickup,
                delivery_type=order.delivery_type,
                is_subscription=is_subscription
            )
            db.session.add(delivery)
        db.session.commit()
        return jsonify({'success': True, 'message': f'Підписку продовжено для клієнта {order.client.instagram}'})
    except Exception as e:
        db.session.rollback()
        logging.error(f'Помилка продовження підписки: {e}')
        return jsonify({'success': False, 'error': 'Помилка при продовженні підписки'}), 500 

@orders_bp.route('/orders/export/csv', methods=['GET'])
@login_required
def export_orders_csv():
    orders = Order.query.options(joinedload(Order.client)).order_by(Order.id.desc()).all()
    def generate():
        header = [
            'ID', 'Instagram', 'Отримувач', 'Телефон', 'Місто', 'Адреса', 'Тип', 'Розмір', 'Сума',
            'Дата першої доставки', 'День', 'Час з', 'Час до', 'Для кого', 'Коментар', 'Побажання', 'Створено', 'Продовжена підписка'
        ]
        yield ','.join(header) + '\n'
        for o in orders:
            row = [
                str(o.id),
                o.client.instagram if o.client else '',
                o.recipient_name or '',
                o.recipient_phone or '',
                o.city or '',
                o.street or '',
                o.delivery_type or '',
                o.size or '',
                str(o.custom_amount) if o.custom_amount else '',
                o.first_delivery_date.strftime('%Y-%m-%d') if o.first_delivery_date else '',
                o.delivery_day or '',
                o.time_from or '',
                o.time_to or '',
                o.for_whom or '',
                (o.comment or '').replace('\n', ' ').replace('\r', ' '),
                (o.preferences or '').replace('\n', ' ').replace('\r', ' '),
                o.created_at.strftime('%Y-%m-%d %H:%M:%S') if o.created_at else '',
                'Так' if getattr(o, 'is_subscription_extended', False) else 'Ні'
            ]
            yield ','.join('"' + str(x).replace('"', '""') + '"' for x in row) + '\n'
    return Response(generate(), mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename=orders_export.csv'
    })

@orders_bp.route('/orders/extend-form-from-delivery/<int:delivery_id>')
@login_required
def extend_form_from_delivery(delivery_id):
    from app.models import Delivery, Order, Client
    delivery = Delivery.query.get_or_404(delivery_id)
    order = delivery.order
    client = delivery.client
    from app.models.settings import Settings
    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()
    return render_template(
        'extend_order_modal.html',
        delivery=delivery,
        order=order,
        client=client,
        cities=cities,
        delivery_types=delivery_types,
        sizes=sizes,
        for_whom=for_whom
    ) 
