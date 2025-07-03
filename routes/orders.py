from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from models import db, Client, Order, Price

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/orders', methods=['GET'])
def orders_list():
    phone = request.args.get('phone', '').strip()
    instagram = request.args.get('instagram', '').strip()
    city = request.args.get('city', '').strip()
    query = Order.query.join(Client)
    if phone:
        query = query.filter(Client.phone.contains(phone))
    if instagram:
        query = query.filter(Client.instagram.contains(instagram))
    if city:
        query = query.filter(Client.city == city)
    orders = query.order_by(Order.id.desc()).all()
    page = int(request.args.get('page', 1))
    per_page = 10
    start = (page - 1) * per_page
    end = start + per_page
    orders_on_page = orders[start:end]
    has_next = end < len(orders)
    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1
    cities = sorted(set(c.city for c in Client.query.all()))
    return render_template('orders_list.html', orders_on_page=orders_on_page, page=page, prev_page=prev_page, next_page=next_page, has_next=has_next, cities=cities)

@orders_bp.route('/orders/new', methods=['POST'])
def order_create():
    instagram = request.form['instagram']
    phone = request.form['phone']
    city = request.form['city']
    client = Client.query.filter_by(instagram=instagram, phone=phone, city=city).first()
    if not client:
        client = Client(instagram=instagram, phone=phone, city=city)
        db.session.add(client)
        db.session.commit()
    order = Order(
        client_id=client.id,
        street=request.form['street'],
        building_number=request.form['building_number'],
        floor=request.form['floor'],
        entrance=request.form['entrance'],
        size=request.form['size'],
        type=request.form['type'],
        comment=request.form['comment'],
        time_window=request.form['time_window']
    )
    db.session.add(order)
    db.session.commit()
    return redirect(url_for('orders.orders_list'))

@orders_bp.route('/orders/<int:order_id>/edit', methods=['GET', 'POST'])
def order_edit(order_id):
    order = Order.query.get_or_404(order_id)
    if request.method == 'POST':
        order.street = request.form['street']
        order.building_number = request.form['building_number']
        order.floor = request.form['floor']
        order.entrance = request.form['entrance']
        order.size = request.form['size']
        order.type = request.form['type']
        order.comment = request.form['comment']
        order.time_window = request.form['time_window']
        order.client.instagram = request.form['instagram']
        order.client.phone = request.form['phone']
        order.client.city = request.form['city']
        db.session.commit()
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
    db.session.delete(order)
    db.session.commit()
    return jsonify({'success': True})

@orders_bp.route('/orders/bouquets', methods=['GET'])
def get_bouquets():
    delivery_type = request.args.get('delivery_type')
    bouquets = Price.query.filter_by(delivery_type=delivery_type).all()
    return jsonify([
        {'id': p.id, 'bouquet_size': p.bouquet_size, 'price': p.price} for p in bouquets
    ]) 