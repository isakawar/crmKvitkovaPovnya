from app.extensions import db
from app.models import Client, Order, Delivery
import datetime
import logging
import calendar
from sqlalchemy import or_

logger = logging.getLogger(__name__)

WEEKDAY_MAP = {'ПН':0, 'ВТ':1, 'СР':2, 'ЧТ':3, 'ПТ':4, 'СБ':5, 'НД':6}
REVERSE_WEEKDAY_MAP = {value: key for key, value in WEEKDAY_MAP.items()}
SUBSCRIPTION_TYPES = ['Weekly', 'Monthly', 'Bi-weekly']
DELIVERY_TYPE_MAP = {
    'Weekly': 7,
    'Bi-weekly': 14,
    'Monthly': 30,
    'One-time': 1
}


def detect_order_scenario(form):
    scenario = (form.get('order_scenario') or '').strip()
    delivery_type = (form.get('delivery_type') or '').strip()
    if scenario in ['subscription', 'order']:
        return scenario
    return 'subscription' if delivery_type in SUBSCRIPTION_TYPES else 'order'


def resolve_delivery_type(form, scenario):
    raw_delivery_type = (form.get('delivery_type') or '').strip()
    if scenario == 'subscription':
        return raw_delivery_type or 'Monthly'
    return raw_delivery_type or 'One-time'


def resolve_delivery_day(form, first_date, scenario):
    raw_delivery_day = (form.get('delivery_day') or '').strip()
    if scenario == 'subscription' and raw_delivery_day:
        return raw_delivery_day
    return REVERSE_WEEKDAY_MAP.get(first_date.weekday(), 'ПН')


def calculate_next_delivery_date(previous_date, delivery_type, desired_weekday):
    if delivery_type == 'Weekly':
        next_date = previous_date + datetime.timedelta(days=7)
        while next_date.weekday() != desired_weekday:
            next_date += datetime.timedelta(days=1)
        return next_date

    if delivery_type == 'Bi-weekly':
        next_date = previous_date + datetime.timedelta(days=14)
        while next_date.weekday() != desired_weekday:
            next_date += datetime.timedelta(days=1)
        return next_date

    if delivery_type == 'Monthly':
        base_date = previous_date + datetime.timedelta(days=28)
        days_forward = (desired_weekday - base_date.weekday()) % 7
        days_backward = (base_date.weekday() - desired_weekday) % 7
        if days_forward <= days_backward:
            return base_date + datetime.timedelta(days=days_forward)
        return base_date - datetime.timedelta(days=days_backward)

    return previous_date


def build_delivery_dates(first_date, delivery_type, delivery_day):
    deliveries = [first_date]
    if delivery_type not in SUBSCRIPTION_TYPES:
        return deliveries

    desired_weekday = WEEKDAY_MAP.get(delivery_day, first_date.weekday())
    previous_date = first_date
    for _ in range(3):
        next_date = calculate_next_delivery_date(previous_date, delivery_type, desired_weekday)
        deliveries.append(next_date)
        previous_date = next_date
    return deliveries

def get_or_create_client(instagram):
    client = Client.query.filter_by(instagram=instagram).first()
    if not client:
        return None, 'Клієнт з таким Instagram не знайдений!'
    return client, None

def check_and_spend_credits(client, bouquet, delivery_count):
    credits_needed = 0
    if client.credits < credits_needed:
        return False, credits_needed
    client.credits -= credits_needed
    db.session.commit()
    return True, credits_needed

def create_order_and_deliveries(client, form):
    logger.info(f'Створення замовлення для клієнта {client.id}')
    
    is_pickup = form.get('is_pickup') == 'on'
    scenario = detect_order_scenario(form)
    first_delivery_date = datetime.datetime.strptime(form['first_delivery_date'], '%Y-%m-%d').date()
    delivery_type = resolve_delivery_type(form, scenario)
    delivery_day = resolve_delivery_day(form, first_delivery_date, scenario)
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
        address_comment=form.get('address_comment'),
        delivery_type=delivery_type,
        size=form['size'],
        custom_amount=int(form.get('custom_amount')) if form.get('custom_amount') and form.get('custom_amount').strip() else None,
        first_delivery_date=first_delivery_date,
        delivery_day=delivery_day,
        time_from=form.get('time_from'),
        time_to=form.get('time_to'),
        comment=form.get('comment'),
        preferences=form.get('preferences'),
        for_whom=form.get('for_whom') or '',
        delivery_method=form.get('delivery_method', 'courier'),
        bouquet_type=form.get('bouquet_type'),
        composition_type=form.get('composition_type'),
    )
    db.session.add(order)
    db.session.commit()

    deliveries = build_delivery_dates(order.first_delivery_date, order.delivery_type, order.delivery_day)

    for i, d_date in enumerate(deliveries):
        delivery_time_from = order.time_from if i == 0 else None
        delivery_time_to = order.time_to if i == 0 else None
        delivery = Delivery(
            order_id=order.id,
            client_id=client.id,
            delivery_date=d_date,
            status='Очікує',
            comment=order.comment if i == 0 else '',
            preferences=order.preferences,
            street=order.street if not order.is_pickup else None,
            building_number=order.building_number if not order.is_pickup else None,
            time_from=delivery_time_from,
            time_to=delivery_time_to,
            size=order.size,
            phone=order.recipient_phone,
            is_pickup=order.is_pickup,
            delivery_type=order.delivery_type,
            is_subscription=order.delivery_type in SUBSCRIPTION_TYPES,
            delivery_method=order.delivery_method,
            address_comment=order.address_comment,
            bouquet_type=order.bouquet_type,
            composition_type=order.composition_type,
        )
        db.session.add(delivery)
    db.session.commit()
    return order

def get_orders(q=None, phone=None, instagram=None, city=None, delivery_type=None, size=None, date_from=None, date_to=None):
    logger.info(f'Фільтрація замовлень: q={q}, phone={phone}, instagram={instagram}, city={city}, delivery_type={delivery_type}, size={size}, date_from={date_from}, date_to={date_to}')
    query = Order.query.join(Client)
    if q:
        like_query = f'%{q}%'
        query = query.filter(or_(
            Client.instagram.ilike(like_query),
            Client.phone.ilike(like_query),
            Order.recipient_name.ilike(like_query),
            Order.recipient_phone.ilike(like_query),
            Order.recipient_social.ilike(like_query),
            Order.city.ilike(like_query),
            Order.street.ilike(like_query),
        ))
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
    if date_from or date_to:
        query = query.join(Delivery)
        if date_from:
            try:
                parsed_date_from = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(Delivery.delivery_date >= parsed_date_from)
            except ValueError:
                logger.warning(f'Некоректний date_from у фільтрі замовлень: {date_from}')
        if date_to:
            try:
                parsed_date_to = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
                query = query.filter(Delivery.delivery_date <= parsed_date_to)
            except ValueError:
                logger.warning(f'Некоректний date_to у фільтрі замовлень: {date_to}')
        query = query.distinct()
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
    scenario = detect_order_scenario(form)
    resolved_delivery_type = resolve_delivery_type(form, scenario)
    resolved_first_delivery_date = datetime.datetime.strptime(form['first_delivery_date'], '%Y-%m-%d').date()
    resolved_delivery_day = resolve_delivery_day(form, resolved_first_delivery_date, scenario)
    order.recipient_name = form['recipient_name']
    order.recipient_phone = form['recipient_phone']
    order.recipient_social = form.get('recipient_social')
    order.city = form['city']
    is_pickup = form.get('is_pickup') == 'on'
    order.street = 'Самовивіз' if is_pickup else form['street']
    order.building_number = form.get('building_number')
    order.floor = form.get('floor')
    order.entrance = form.get('entrance')
    order.is_pickup = is_pickup
    order.address_comment = form.get('address_comment')
    order.bouquet_type = form.get('bouquet_type')
    order.composition_type = form.get('composition_type')
    order.delivery_type = resolved_delivery_type
    order.size = form['size']
    order.custom_amount = int(form.get('custom_amount')) if form.get('custom_amount') and form.get('custom_amount').strip() else None
    order.first_delivery_date = resolved_first_delivery_date
    order.delivery_day = resolved_delivery_day
    order.time_from = form.get('time_from')
    order.time_to = form.get('time_to')
    order.comment = form.get('comment')
    order.preferences = form.get('preferences')
    order.for_whom = form['for_whom']
    if form.get('delivery_method'):
        order.delivery_method = form.get('delivery_method')
    db.session.commit()
    return order

def delete_order(order):
    logger.warning(f'Видалення замовлення {order.id}')
    db.session.delete(order)
    db.session.commit() 
