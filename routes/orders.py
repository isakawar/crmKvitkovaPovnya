from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from models import db, Client, Order, Price, Delivery
import datetime

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

@orders_bp.route('/orders/new', methods=['GET'])
def order_form():
    bouquets = Price.query.all()
    return render_template('order_form.html', bouquets=bouquets)

@orders_bp.route('/orders/new', methods=['POST'])
def order_create():
    print('--- ORDER CREATE ---')
    print('Form data:', dict(request.form))
    phone = request.form['phone']
    city = request.form['city']
    instagram = request.form.get('instagram')
    client = Client.query.filter_by(phone=phone).first()
    if not client:
        print('Creating new client')
        client = Client(phone=phone, city=city, instagram=instagram or '')
        db.session.add(client)
        db.session.commit()
    else:
        print('Updating existing client')
        if client.city != city:
            client.city = city
        if instagram and client.instagram != instagram:
            client.instagram = instagram
        db.session.commit()
    delivery_count = int(request.form.get('delivery_count', 1))
    bouquet_id = request.form.get('bouquet_id')
    bouquet = Price.query.get(bouquet_id) if bouquet_id else None
    print('Bouquet:', bouquet)
    credits_needed = bouquet.price * delivery_count if bouquet else 0
    print('Credits needed:', credits_needed, 'Client credits:', client.credits)
    if client.credits < credits_needed:
        print('Not enough credits!')
        flash('Недостатньо кредитів для створення замовлення!', 'danger')
        return redirect('/orders')
    client.credits -= credits_needed
    db.session.commit()
    # Створення замовлення
    order = Order(
        client_id=client.id,
        street=request.form['street'],
        building_number=request.form['building_number'],
        floor=request.form.get('floor'),
        entrance=request.form['entrance'],
        size=request.form.get('size'),
        type=request.form['type'],
        comment=request.form['comment'],
        time_window=request.form.get('time_window'),
        bouquet_id=bouquet_id,
        delivery_count=delivery_count,
        recipient_phone=request.form.get('recipient_phone'),
        periodicity=request.form.get('periodicity'),
        preferred_days=','.join(request.form.getlist('preferred_days')),
        time_from=request.form.get('time_from'),
        time_to=request.form.get('time_to')
    )
    db.session.add(order)
    db.session.commit()
    print('Order created:', order.id)
    # Створення доставок з датами
    preferred_days = request.form.getlist('preferred_days')
    print('Preferred days:', preferred_days)
    weekday_map = {'пн':0, 'вт':1, 'ср':2, 'чт':3, 'пт':4, 'сб':5, 'нд':6}
    days = [weekday_map[d] for d in preferred_days if d in weekday_map]
    print('Days (as int):', days)
    if not days:
        days = [datetime.date.today().weekday()]
        print('No preferred days, using today:', days)
    periodicity = request.form.get('periodicity') or '1/7'
    start_date = datetime.date.today()
    created = 0
    i = 0
    while created < delivery_count:
        d = start_date + datetime.timedelta(days=i)
        if d.weekday() in days:
            if periodicity == '1/14' and created > 0:
                d = d + datetime.timedelta(days=7*(created))
            print(f'Creating delivery {created+1}: date={d}, order_id={order.id}, client_id={client.id}, bouquet_id={bouquet.id if bouquet else None}')
            delivery = Delivery(
                order_id=order.id,
                client_id=client.id,
                bouquet_id=bouquet.id if bouquet else None,
                delivery_date=d,
                status='Очікує',
                comment=request.form.get('comment', '')
            )
            db.session.add(delivery)
            created += 1
        i += 1
    db.session.commit()
    print('Total deliveries created:', created)
    flash('Замовлення створено, доставки додано!', 'success')
    return redirect('/orders')

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