from app.extensions import db
from app.models import Client, Order, Delivery
import datetime
import logging
import calendar

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
    credits_needed = 0
    if client.credits < credits_needed:
        return False, credits_needed
    client.credits -= credits_needed
    db.session.commit()
    return True, credits_needed

def create_order_and_deliveries(client, form):
    logger.info(f'Створення замовлення для клієнта {client.id}')
    
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

    delivery_type = form['delivery_type']
    first_date = order.first_delivery_date
    desired_weekday = WEEKDAY_MAP.get(order.delivery_day, 0)
    deliveries = []

    # Перша доставка — це дата, яку ввів користувач
    deliveries.append(first_date)

    if delivery_type != 'One-Time':
        count = 5  # Змінено з 4 на 5 для підписок
        prev_date = first_date
        for i in range(1, count):
            if delivery_type == 'Weekly':
                # Наступний тиждень, потрібний день
                next_date = prev_date + datetime.timedelta(days=1)
                while next_date.weekday() != desired_weekday:
                    next_date += datetime.timedelta(days=1)
            elif delivery_type == 'Bi-weekly':
                # Через тиждень, потрібний день
                next_date = prev_date + datetime.timedelta(days=8)  # мінімум через тиждень
                while next_date.weekday() != desired_weekday:
                    next_date += datetime.timedelta(days=1)
            elif delivery_type == 'Monthly':
                # Наступний місяць, потрібний день
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
        # Визначаємо статус залежно від типу доставки та порядкового номера
        if delivery_type == 'One-Time':
            status = 'Очікує'
        elif delivery_type in ['Weekly', 'Monthly', 'Bi-weekly']:
            # Перші 4 доставки - статус 'Очікує', 5-та - 'Не оплачена'
            if i < 4:
                status = 'Очікує'
            else:
                status = 'Не оплачена'
        else:
            status = 'Очікує'  # Для інших типів
        
        # Визначаємо чи це підписка для підписних типів
        is_subscription = False
        if delivery_type in ['Weekly', 'Monthly', 'Bi-weekly']:
            # Перші 4 доставки - оплачені (is_subscription=True), 5-та - не оплачена (is_subscription=False)
            is_subscription = i < 4
        
        delivery = Delivery(
            order_id=order.id,
            client_id=client.id,
            delivery_date=d_date,
            status=status,
            comment=order.comment if i == 0 else '',
            preferences=order.preferences,
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