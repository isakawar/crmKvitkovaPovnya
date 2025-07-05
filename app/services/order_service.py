from app.extensions import db
from app.models import Client, Order, Price, Delivery
import datetime
import logging

logger = logging.getLogger(__name__)

WEEKDAY_MAP = {'ПН':0, 'ВТ':1, 'СР':2, 'ЧТ':3, 'ПТ':4, 'СБ':5, 'НД':6}
DELIVERY_TYPE_MAP = {
    'Weekly': 7,
    'Bi-weekly': 14,
    'Monthly': 30,
    'One-time': 1
}

def get_or_create_client(instagram):
    client = Client.query.filter_by(instagram=instagram).first()
    if not client:
        return None, 'Клієнт з таким Instagram не знайдений!'
    return client, None

def check_and_spend_credits(client, bouquet, delivery_count):
    credits_needed = bouquet.price * delivery_count if bouquet else 0
    if client.credits < credits_needed:
        return False, credits_needed
    client.credits -= credits_needed
    db.session.commit()
    return True, credits_needed

def create_order_and_deliveries(client, form):
    logger.info(f'Створення замовлення для клієнта {client.id}')
    
    # Створюємо замовлення
    is_pickup = form.get('is_pickup') == 'on'
    order = Order(
        client_id=client.id,
        recipient_name=form['recipient_name'],
        recipient_phone=form['recipient_phone'],
        recipient_social=form.get('recipient_social'),
        city=form['city'],
        street='Самовивіз' if is_pickup else form['street'],
        building_number=form.get('building_number'),
        floor=form.get('floor'),
        entrance=form.get('entrance'),
        is_pickup=is_pickup,
        delivery_type=form['delivery_type'],
        size=form['size'],
        custom_amount=int(form.get('custom_amount', 0)) if form.get('custom_amount') else None,
        first_delivery_date=datetime.datetime.strptime(form['first_delivery_date'], '%Y-%m-%d').date(),
        delivery_day=form['delivery_day'],
        time_from=form.get('time_from'),
        time_to=form.get('time_to'),
        comment=form.get('comment'),
        preferences=form.get('preferences'),
        for_whom=form['for_whom']
    )
    db.session.add(order)
    db.session.commit()
    
    # Створюємо доставки
    delivery_type = form['delivery_type']
    days_between = DELIVERY_TYPE_MAP.get(delivery_type, 7)
    first_date = order.first_delivery_date
    weekday = WEEKDAY_MAP.get(order.delivery_day, 0)
    
    # Розраховуємо кількість доставок
    if delivery_type == 'One-time':
        delivery_count = 1
    else:
        # Для підписок - 12 доставок
        delivery_count = 12
    
    created = 0
    current_date = first_date
    
    while created < delivery_count:
        if current_date.weekday() == weekday:
            delivery = Delivery(
                order_id=order.id,
                client_id=client.id,
                delivery_date=current_date,
                status='Очікує',
                comment=order.comment,
                street=order.street if not order.is_pickup else None,
                building_number=order.building_number if not order.is_pickup else None,
                time_from=order.time_from,
                time_to=order.time_to,
                size=order.size,
                phone=order.recipient_phone,
                is_pickup=order.is_pickup
            )
            db.session.add(delivery)
            created += 1
        
        # Переходимо до наступної дати
        if delivery_type == 'One-time':
            break
        elif delivery_type == 'Weekly':
            current_date += datetime.timedelta(days=7)
        elif delivery_type == 'Bi-weekly':
            current_date += datetime.timedelta(days=14)
        elif delivery_type == 'Monthly':
            # Додаємо місяць
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
    
    db.session.commit()
    return order

def get_orders(phone=None, instagram=None, city=None, delivery_type=None, size=None):
    logger.info(f'Фільтрація замовлень: phone={phone}, instagram={instagram}, city={city}, delivery_type={delivery_type}, size={size}')
    query = Order.query.join(Client)
    if phone:
        query = query.filter(Order.recipient_phone.contains(phone))
    if instagram:
        query = query.filter(Client.instagram.contains(instagram))
    if city:
        query = query.filter(Order.city == city)
    if delivery_type:
        query = query.filter(Order.delivery_type == delivery_type)
    if size:
        query = query.filter(Order.size == size)
    return query.order_by(Order.id.desc()).all()

def paginate_orders(orders, page=1, per_page=10):
    start = (page - 1) * per_page
    end = start + per_page
    return orders[start:end], end < len(orders)

def update_order(order, form):
    # Оновлення клієнта, якщо змінено Instagram
    new_instagram = form.get('client_instagram')
    if new_instagram and new_instagram != order.client.instagram:
        new_client = Client.query.filter_by(instagram=new_instagram).first()
        if not new_client:
            raise ValueError('Клієнта з таким Instagram не знайдено!')
        order.client_id = new_client.id
    order.recipient_name = form['recipient_name']
    order.recipient_phone = form['recipient_phone']
    order.recipient_social = form.get('recipient_social')
    order.city = form['city']
    order.street = form['street']
    order.building_number = form.get('building_number')
    order.floor = form.get('floor')
    order.entrance = form.get('entrance')
    order.is_pickup = form.get('is_pickup') == 'on'
    order.delivery_type = form['delivery_type']
    order.size = form['size']
    order.custom_amount = int(form.get('custom_amount', 0)) if form.get('custom_amount') else None
    order.first_delivery_date = datetime.datetime.strptime(form['first_delivery_date'], '%Y-%m-%d').date()
    order.delivery_day = form['delivery_day']
    order.time_from = form.get('time_from')
    order.time_to = form.get('time_to')
    order.comment = form.get('comment')
    order.preferences = form.get('preferences')
    order.for_whom = form['for_whom']
    db.session.commit()
    return order

def delete_order(order):
    logger.warning(f'Видалення замовлення {order.id}')
    db.session.delete(order)
    db.session.commit()

def get_bouquets_by_type(delivery_type):
    return Price.query.filter_by(delivery_type=delivery_type).all() 