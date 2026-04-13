from app.extensions import db
from app.models import Client, Order, Delivery
from app.models.recipient_phone import RecipientPhone
import datetime
import logging
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)

# Kept for imports in other modules
SUBSCRIPTION_TYPES = ['Weekly', 'Monthly', 'Bi-weekly']


def get_or_create_client(instagram):
    client = Client.query.filter_by(instagram=instagram).first()
    if not client:
        return None, 'Клієнт з таким Instagram не знайдений!'
    return client, None


def create_order_and_deliveries(client, form):
    """Create a single (one-time) order with one delivery."""
    logger.info(f'Creating one-time order for client {client.id}')

    is_pickup = form.get('is_pickup') == 'on'
    delivery_date = datetime.datetime.strptime(form['first_delivery_date'], '%Y-%m-%d').date()

    custom_amount_raw = (form.get('custom_amount') or '').strip()
    custom_amount = int(custom_amount_raw) if custom_amount_raw else None

    discount_raw = (form.get('discount') or '').strip()
    discount = int(discount_raw) if discount_raw else None

    order = Order(
        client_id=client.id,
        recipient_name=form['recipient_name'],
        recipient_phone=form['recipient_phone'],
        recipient_social=form.get('recipient_social') or None,
        city=form['city'],
        street='Самовивіз' if is_pickup else (form.get('street') or ''),
        building_number=form.get('building_number') or None,
        floor=form.get('floor') or None,
        entrance=form.get('entrance') or None,
        is_pickup=is_pickup,
        address_comment=form.get('address_comment') or None,
        delivery_method=form.get('delivery_method') or 'courier',
        size=form['size'],
        custom_amount=custom_amount,
        delivery_date=delivery_date,
        time_from=form.get('time_from') or None,
        time_to=form.get('time_to') or None,
        bouquet_type=form.get('bouquet_type') or None,
        composition_type=form.get('composition_type') or None,
        for_whom=form.get('for_whom') or '',
        comment=form.get('comment') or None,
        preferences=form.get('preferences') or None,
        discount=discount,
    )
    db.session.add(order)
    db.session.flush()

    for i, ph in enumerate(
        form.getlist('additional_phones') if hasattr(form, 'getlist') else form.get('additional_phones', []),
        start=1
    ):
        if ph.strip():
            db.session.add(RecipientPhone(order_id=order.id, phone=ph.strip(), position=i))

    delivery = Delivery(
        order_id=order.id,
        client_id=client.id,
        delivery_date=delivery_date,
        status='Очікує',
        comment=order.comment,
        preferences=order.preferences,
        street=order.street if not order.is_pickup else None,
        building_number=order.building_number if not order.is_pickup else None,
        floor=order.floor if not order.is_pickup else None,
        entrance=order.entrance if not order.is_pickup else None,
        time_from=order.time_from,
        time_to=order.time_to,
        size=order.size,
        phone=order.recipient_phone,
        is_pickup=order.is_pickup,
        delivery_method=order.delivery_method,
        address_comment=order.address_comment,
        bouquet_type=order.bouquet_type,
        composition_type=order.composition_type,
    )
    db.session.add(delivery)
    db.session.commit()
    return order


def get_orders(q=None, phone=None, instagram=None, city=None, size=None, delivery_type=None, date_from=None, date_to=None):
    from app.models.subscription import Subscription as _Subscription
    query = Order.query.options(joinedload(Order.client)).join(Client)
    if q:
        like_q = f'%{q}%'
        query = query.filter(or_(
            Client.instagram.ilike(like_q),
            Client.phone.ilike(like_q),
            Order.recipient_name.ilike(like_q),
            Order.recipient_phone.ilike(like_q),
            Order.recipient_social.ilike(like_q),
            Order.city.ilike(like_q),
            Order.street.ilike(like_q),
        ))
    if phone:
        query = query.filter(Order.recipient_phone.contains(phone))
    if instagram:
        query = query.filter(Client.instagram.contains(instagram))
    if city:
        query = query.filter(Order.city == city)
    if size:
        query = query.filter(Order.size == size)
    if delivery_type:
        if delivery_type in SUBSCRIPTION_TYPES:
            query = query.join(_Subscription, _Subscription.id == Order.subscription_id).filter(_Subscription.type == delivery_type)
        elif delivery_type == 'One-time':
            query = query.filter(Order.subscription_id.is_(None))
    if date_from or date_to:
        query = query.join(Delivery)
        if date_from:
            try:
                parsed = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(Delivery.delivery_date >= parsed)
            except ValueError:
                pass
        if date_to:
            try:
                parsed = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
                query = query.filter(Delivery.delivery_date <= parsed)
            except ValueError:
                pass
        query = query.distinct()
    return query.order_by(Order.id.desc()).all()


def paginate_orders(orders, page=1, per_page=10):
    start = (page - 1) * per_page
    end = start + per_page
    return orders[start:end], end < len(orders)


def update_order(order, form):
    new_instagram = form.get('client_instagram')
    if new_instagram and new_instagram != order.client.instagram:
        new_client = Client.query.filter_by(instagram=new_instagram).first()
        if not new_client:
            raise ValueError('Клієнта з таким Instagram не знайдено!')
        order.client_id = new_client.id

    delivery_date = datetime.datetime.strptime(form['first_delivery_date'], '%Y-%m-%d').date()
    is_pickup = form.get('is_pickup') == 'on'

    order.recipient_name = form['recipient_name']
    order.recipient_phone = form['recipient_phone']
    order.recipient_social = form.get('recipient_social') or None

    RecipientPhone.query.filter_by(order_id=order.id).delete()
    for i, ph in enumerate(
        form.getlist('additional_phones') if hasattr(form, 'getlist') else form.get('additional_phones', []),
        start=1
    ):
        if ph.strip():
            db.session.add(RecipientPhone(order_id=order.id, phone=ph.strip(), position=i))

    order.city = form.get('city') or order.city
    order.street = 'Самовивіз' if is_pickup else (form.get('street') or '')
    order.building_number = form.get('building_number') or None
    order.floor = form.get('floor') or None
    order.entrance = form.get('entrance') or None
    order.is_pickup = is_pickup
    order.address_comment = form.get('address_comment') or None
    order.bouquet_type = form.get('bouquet_type') or None
    order.composition_type = form.get('composition_type') or None
    order.size = form['size']
    order.custom_amount = (
        int(form.get('custom_amount'))
        if form.get('custom_amount') and str(form.get('custom_amount')).strip()
        else None
    )
    order.delivery_date = delivery_date
    order.time_from = form.get('time_from') or None
    order.time_to = form.get('time_to') or None
    order.comment = form.get('comment') or None
    order.preferences = form.get('preferences') or None
    order.for_whom = form.get('for_whom') or order.for_whom
    if form.get('delivery_method'):
        order.delivery_method = form.get('delivery_method')

    active_deliveries = [d for d in order.deliveries if d.status not in ['Доставлено', 'Скасовано']]
    for i, delivery in enumerate(sorted(active_deliveries, key=lambda d: d.delivery_date or datetime.date.min)):
        if i == 0:
            delivery.delivery_date = delivery_date
        delivery.comment = order.comment
        delivery.preferences = order.preferences
        delivery.address_comment = order.address_comment
        delivery.street = order.street if not order.is_pickup else None
        delivery.building_number = order.building_number if not order.is_pickup else None
        delivery.floor = order.floor if not order.is_pickup else None
        delivery.entrance = order.entrance if not order.is_pickup else None
        delivery.is_pickup = order.is_pickup
        delivery.phone = order.recipient_phone
        delivery.delivery_method = order.delivery_method
        delivery.bouquet_type = order.bouquet_type
        delivery.composition_type = order.composition_type
        delivery.time_from = order.time_from
        delivery.time_to = order.time_to

    db.session.commit()
    return order


def delete_order(order):
    logger.warning(f'Deleting order {order.id}')
    from app.models.delivery_route import RouteDelivery
    for delivery in list(order.deliveries):
        RouteDelivery.query.filter_by(delivery_id=delivery.id).delete()
        db.session.delete(delivery)
    RecipientPhone.query.filter_by(order_id=order.id).delete()
    db.session.flush()
    db.session.delete(order)
    db.session.commit()
