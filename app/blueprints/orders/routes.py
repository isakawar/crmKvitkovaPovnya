from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from app.extensions import db
from app.models import Order, Client, Delivery
import logging
from app.services.order_service import get_orders, paginate_orders, update_order, delete_order, get_or_create_client, create_order_and_deliveries

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/orders', methods=['GET'])
def orders_list():
    phone = request.args.get('phone', '').strip()
    instagram = request.args.get('instagram', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 30
    all_orders_count = Order.query.count()
    orders = get_orders(phone, instagram)
    orders_on_page, has_next = paginate_orders(orders, page, per_page)
    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1
    return render_template('orders_list.html', orders_on_page=orders_on_page, page=page, prev_page=prev_page, next_page=next_page, has_next=has_next, orders_count=all_orders_count)

@orders_bp.route('/orders/new', methods=['GET'])
def order_form():
    clients = Client.query.all()
    return render_template('order_form.html', clients=clients)

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
        'for_whom': order.for_whom
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