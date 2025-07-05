from app.extensions import db
from app.models import Delivery, Courier
from datetime import datetime, timedelta
import logging
from app.models.client import Client

logger = logging.getLogger(__name__)

def get_financial_week_dates(offset=0):
    """Отримати дати фінансового тижня (п'ятниця-п'ятниця, не включно)"""
    today = datetime.now().date()
    weekday = today.weekday()  # 0=Monday, ..., 4=Friday, 6=Sunday

    # Знаходимо останню п'ятницю (до або включно сьогодні)
    days_since_friday = (weekday - 4) % 7
    current_friday = today - timedelta(days=days_since_friday) + timedelta(days=offset*7)
    end_date = current_friday + timedelta(days=7)  # до наступної п'ятниці (НЕ включно)
    return current_friday, end_date

def get_deliveries(date_str=None, client_instagram=None, recipient_phone=None, financial_week=None):
    deliveries_query = Delivery.query
    selected_date = None
    start_date = end_date = None

    if client_instagram:
        deliveries_query = deliveries_query.join(Client).filter(Client.instagram.contains(client_instagram))
    if recipient_phone:
        deliveries_query = deliveries_query.filter(Delivery.phone.contains(recipient_phone))

    if financial_week is not None:
        start_date, end_date = get_financial_week_dates(financial_week)
        logger.info(f'Фільтрація по фінансовому тижню: {financial_week}, період: {start_date} - {end_date}')
        deliveries_query = deliveries_query.filter(
            Delivery.delivery_date >= start_date,
            Delivery.delivery_date < end_date
        )
    elif date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            deliveries_query = deliveries_query.filter(Delivery.delivery_date == selected_date)
        except Exception as e:
            logger.warning(f'Помилка парсингу дати: {e}')

    logger.info(f'Фінальний SQL: {str(deliveries_query)}')
    result = deliveries_query.order_by(Delivery.id.desc()).all()
    logger.info(f'Кількість доставок після фільтрації: {len(result)}')
    return result, date_str or ''

def get_delivery_by_id(delivery_id):
    return Delivery.query.get_or_404(delivery_id)

def update_delivery(d, data):
    logger.info(f'Оновлення доставки {d.id} даними: {data}')
    if 'delivery_date' in data:
        d.delivery_date = datetime.strptime(data['delivery_date'], '%Y-%m-%d').date()
    if 'time_from' in data:
        d.time_from = data['time_from']
    if 'time_to' in data:
        d.time_to = data['time_to']
    if 'street' in data:
        d.street = data['street']
    if 'phone' in data:
        d.phone = data['phone']
    if 'size' in data:
        d.size = data['size']
    if 'delivery_type' in data:
        d.delivery_type = data['delivery_type']
    if 'status' in data:
        d.status = data['status']
    if 'is_pickup' in data:
        d.is_pickup = data['is_pickup']
    if 'is_subscription' in data:
        d.is_subscription = data['is_subscription']
    if 'comment' in data:
        d.comment = data['comment']
    if 'preferences' in data:
        d.preferences = data['preferences']
    db.session.commit()
    return d

def set_delivery_status(d, new_status):
    logger.info(f'Зміна статусу доставки {d.id} на {new_status}')
    prev_status = d.status
    d.status = new_status
    d.status_changed_at = datetime.utcnow()
    # Якщо статус змінюється з 'Розподілено' на 'Доставлено' і є кур'єр
    if prev_status == 'Розподілено' and new_status == 'Доставлено' and d.courier_id:
        courier = Courier.query.get(d.courier_id)
        if courier:
            courier.deliveries_count = (courier.deliveries_count or 0) + 1
    # Якщо статус стає 'Доставлено', фіксуємо час доставки
    if new_status == 'Доставлено' and not d.delivered_at:
        d.delivered_at = datetime.utcnow()
    db.session.commit()
    return d

def assign_deliveries(assignments):
    logger.info(f'Розподіл доставок: {assignments}')
    # Скидаємо всі призначення
    for d in Delivery.query.all():
        d.courier_id = None
        d.status = 'Очікує'
    db.session.commit()
    # Призначаємо доставки кур'єрам
    for courier_id, delivery_ids in assignments.items():
        if courier_id == 'unassigned':
            for d_id in delivery_ids:
                d = Delivery.query.get(int(d_id))
                if d:
                    d.courier_id = None
                    d.status = 'Очікує'
        else:
            for d_id in delivery_ids:
                d = Delivery.query.get(int(d_id))
                if d:
                    d.courier_id = int(courier_id)
                    d.status = 'Розподілено'
    db.session.commit()
    return True

def get_all_deliveries_ordered():
    return Delivery.query.order_by(Delivery.delivery_date).all()

def get_all_couriers():
    return Courier.query.all()

def assign_courier_to_deliveries(delivery_ids, courier_id):
    try:
        for d_id in delivery_ids:
            d = Delivery.query.get(int(d_id))
            if d:
                d.courier_id = int(courier_id)
                d.status = 'Розподілено'
        db.session.commit()
        return True, None
    except Exception as e:
        db.session.rollback()
        return False, str(e) 