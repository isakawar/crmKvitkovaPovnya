from app.extensions import db
from app.models import Client, Order, Price, Delivery
import datetime
import logging

logger = logging.getLogger(__name__)

WEEKDAY_MAP = {'пн':0, 'вт':1, 'ср':2, 'чт':3, 'пт':4, 'сб':5, 'нд':6}

def get_or_create_client(phone, city, instagram):
    client = Client.query.filter_by(phone=phone).first()
    if not client:
        client = Client(phone=phone, city=city, instagram=instagram or '')
        db.session.add(client)
        db.session.commit()
    else:
        if client.city != city:
            client.city = city
        if instagram and client.instagram != instagram:
            client.instagram = instagram
        db.session.commit()
    return client

def check_and_spend_credits(client, bouquet, delivery_count):
    credits_needed = bouquet.price * delivery_count if bouquet else 0
    if client.credits < credits_needed:
        return False, credits_needed
    client.credits -= credits_needed
    db.session.commit()
    return True, credits_needed

def create_order_and_deliveries(client, form):
    logger.info(f'Створення замовлення для клієнта {client.id}')
    delivery_count = int(form.get('delivery_count', 1))
    bouquet_id = form.get('bouquet_id')
    bouquet = None
    if bouquet_id:
        bouquet = Price.query.get(bouquet_id)
    order = Order(
        client_id=client.id,
        street=form['street'],
        building_number=form.get('building_number'),
        floor=form.get('floor'),
        entrance=form.get('entrance'),
        size=form.get('size'),
        type=form.get('type'),
        comment=form.get('comment'),
        time_window=form.get('time_window'),
        recipient_phone=form.get('recipient_phone'),
        periodicity=form.get('periodicity'),
        preferred_days=form.get('preferred_days'),
        time_from=form.get('time_from'),
        time_to=form.get('time_to'),
        bouquet_id=bouquet.id if bouquet else None,
        delivery_count=delivery_count,
        bouquet_size=bouquet.bouquet_size if bouquet else None,
        delivery_type=bouquet.delivery_type if bouquet else None,
        price_at_order=bouquet.price if bouquet else None
    )
    db.session.add(order)
    db.session.commit()
    # Доставки
    preferred_days = form.getlist('preferred_days')
    days = [WEEKDAY_MAP[d] for d in preferred_days if d in WEEKDAY_MAP]
    if not days:
        days = [datetime.date.today().weekday()]
    periodicity = form.get('periodicity') or '1/7'
    start_date = datetime.date.today()
    created = 0
    i = 0
    deliveries = []
    while created < delivery_count:
        d_date = start_date + datetime.timedelta(days=i)
        if d_date.weekday() in days:
            if periodicity == '1/14' and created > 0:
                d_date = d_date + datetime.timedelta(days=7*(created))
            delivery = Delivery(
                order_id=order.id,
                client_id=client.id,
                bouquet_id=bouquet.id if bouquet else None,
                delivery_date=d_date,
                status='Очікує',
                comment=form.get('comment', ''),
                street=order.street,
                building_number=order.building_number,
                time_window=order.time_window,
                size=order.size,
                phone=order.recipient_phone,
                bouquet_size=bouquet.bouquet_size if bouquet else None,
                delivery_type=bouquet.delivery_type if bouquet else None,
                price_at_delivery=bouquet.price if bouquet else None
            )
            db.session.add(delivery)
            deliveries.append(delivery)
            created += 1
        i += 1
    db.session.commit()
    return order

def get_orders(phone=None, instagram=None, city=None):
    logger.info(f'Фільтрація замовлень: phone={phone}, instagram={instagram}, city={city}')
    query = Order.query.join(Client)
    if phone:
        query = query.filter(Client.phone.contains(phone))
    if instagram:
        query = query.filter(Client.instagram.contains(instagram))
    if city:
        query = query.filter(Client.city == city)
    return query.order_by(Order.id.desc()).all()

def paginate_orders(orders, page=1, per_page=10):
    start = (page - 1) * per_page
    end = start + per_page
    return orders[start:end], end < len(orders)

def update_order(order, form):
    order.street = form['street']
    order.building_number = form['building_number']
    order.floor = form['floor']
    order.entrance = form['entrance']
    order.size = form['size']
    order.type = form['type']
    order.comment = form['comment']
    order.time_window = form['time_window']
    order.client.instagram = form['instagram']
    order.client.phone = form['phone']
    order.client.city = form['city']
    db.session.commit()
    return order

def delete_order(order):
    logger.warning(f'Видалення замовлення {order.id}')
    db.session.delete(order)
    db.session.commit()

def get_bouquets_by_type(delivery_type):
    return Price.query.filter_by(delivery_type=delivery_type).all() 