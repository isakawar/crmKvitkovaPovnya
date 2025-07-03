from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from app.extensions import db
from app.models import Order, Client, Price, Delivery
import logging
from app.services.order_service import get_orders, paginate_orders, update_order, delete_order, get_bouquets_by_type, get_or_create_client, check_and_spend_credits, create_order_and_deliveries

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/orders', methods=['GET'])
def orders_list():
    phone = request.args.get('phone', '').strip()
    instagram = request.args.get('instagram', '').strip()
    city = request.args.get('city', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 10
    orders = get_orders(phone, instagram, city)
    orders_on_page, has_next = paginate_orders(orders, page, per_page)
    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1
    cities = sorted(set(c.city for c in Client.query.all()))
    return render_template('orders_list.html', orders_on_page=orders_on_page, page=page, prev_page=prev_page, next_page=next_page, has_next=has_next, cities=cities)

@orders_bp.route('/orders/new', methods=['GET'])
def order_form():
    bouquets = Price.query.all()
    return render_template('order_form.html', bouquets=bouquets)

@orders_bp.route('/orders/new', methods=['POST'])
def order_create():
    logging.info('--- ORDER CREATE ---')
    logging.info(f'Form data: {dict(request.form)}')
    phone = request.form['phone']
    city = request.form['city']
    instagram = request.form.get('instagram')
    client = get_or_create_client(phone, city, instagram)
    bouquet_id = request.form.get('bouquet_id')
    bouquet = None
    if bouquet_id:
        bouquet = Price.query.get(bouquet_id)
    delivery_count = int(request.form.get('delivery_count', 1))
    ok, credits_needed = check_and_spend_credits(client, bouquet, delivery_count)
    if not ok:
        logging.warning('Not enough credits!')
        flash('Недостатньо кредитів для створення замовлення!', 'danger')
        return redirect('/orders')
    order = create_order_and_deliveries(client, request.form)
    logging.info(f'Order created: {order.id}')
    flash('Замовлення створено, доставки додано!', 'success')
    return redirect('/orders')

@orders_bp.route('/orders/<int:order_id>/edit', methods=['GET', 'POST'])
def order_edit(order_id):
    order = Order.query.get_or_404(order_id)
    if request.method == 'POST':
        update_order(order, request.form)
        return jsonify({'success': True})
    return jsonify({
        'id': order.id,
        'instagram': order.client.instagram,
        'phone': order.client.phone,
        'city': order.client.city,
        'street': order.street,
        'building_number': order.building_number,
        'floor': order.floor,
        'entrance': order.entrance,
        'size': order.size,
        'type': order.type,
        'comment': order.comment,
        'time_window': order.time_window
    })

@orders_bp.route('/orders/<int:order_id>/delete', methods=['POST'])
def order_delete(order_id):
    order = Order.query.get_or_404(order_id)
    delete_order(order)
    return jsonify({'success': True})

@orders_bp.route('/orders/bouquets', methods=['GET'])
def get_bouquets():
    delivery_type = request.args.get('delivery_type')
    bouquets = get_bouquets_by_type(delivery_type)
    return jsonify([
        {'id': p.id, 'bouquet_size': p.bouquet_size, 'price': p.price} for p in bouquets
    ]) 