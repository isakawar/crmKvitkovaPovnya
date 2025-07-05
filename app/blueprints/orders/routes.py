from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, Response
from app.extensions import db
from app.models import Order, Client, Delivery
from app.models.settings import Settings
import logging
from app.services.order_service import get_orders, paginate_orders, update_order, delete_order, get_or_create_client, create_order_and_deliveries
import csv
from sqlalchemy.orm import joinedload

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/orders', methods=['GET'])
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
def order_form():
    clients = Client.query.all()
    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()
    return render_template('order_form.html', clients=clients, cities=cities, delivery_types=delivery_types, sizes=sizes, for_whom=for_whom)

@orders_bp.route('/orders/new', methods=['POST'])
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
        'can_extend_subscription': can_extend_subscription
    })

@orders_bp.route('/orders/<int:order_id>/delete', methods=['POST'])
def order_delete(order_id):
    order = Order.query.get_or_404(order_id)
    delete_order(order)
    return jsonify({'success': True})

@orders_bp.route('/clients/search', methods=['GET'])
def search_clients():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    
    clients = Client.query.filter(Client.instagram.contains(query)).limit(10).all()
    return jsonify([{'instagram': c.instagram} for c in clients])

@orders_bp.route('/route-generator', methods=['GET', 'POST'])
def route_generator():
    if request.method == 'POST':
        # Тут можна додати обробку CSV-файлу та розрахунок маршруту
        # file = request.files.get('csv_file')
        # couriers = request.form.get('couriers')
        # start_time = request.form.get('start_time')
        # TODO: Додати логіку обробки
        return render_template('route_generator.html', result='(Тут буде результат)')
    return render_template('route_generator.html')

@orders_bp.route('/orders/<int:order_id>/extend-subscription', methods=['POST'])
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
                comment=order.comment,
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