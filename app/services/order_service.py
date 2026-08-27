from app.extensions import db
from app.models import Client, Order, Delivery
from app.models.recipient_phone import RecipientPhone
import datetime
import logging
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)

from app.services.subscription_service import SUBSCRIPTION_TYPES  # noqa: F401


def _order_snapshot(order) -> dict:
    client = order.client
    return {
        'client_id': order.client_id,
        'client_name': (client.name or client.instagram or '') if client else '',
        'client_instagram': client.instagram if client else '',
        'client_telegram': client.telegram if client else '',
        'client_phone': client.phone if client else '',
        'size': order.size,
        'custom_amount': order.custom_amount,
        'charged_amount': str(order.charged_amount) if order.charged_amount is not None else None,
        'discount': order.discount,
        'delivery_date': str(order.delivery_date) if order.delivery_date else None,
        'time_from': order.time_from,
        'time_to': order.time_to,
        'city': order.city,
        'street': order.street,
        'building_number': order.building_number,
        'floor': order.floor,
        'entrance': order.entrance,
        'is_pickup': order.is_pickup,
        'address_comment': order.address_comment,
        'delivery_method': order.delivery_method,
        'recipient_name': order.recipient_name,
        'recipient_phone': order.recipient_phone,
        'recipient_social': order.recipient_social,
        'for_whom': order.for_whom,
        'bouquet_type': order.bouquet_type,
        'composition_type': order.composition_type,
        'comment': order.comment,
        'preferences': order.preferences,
    }


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

    from app.services.billing_service import get_order_price
    order.charged_amount = get_order_price(order)

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

    from flask_login import current_user
    from app.services.activity_log_service import log as _log
    _log(
        current_user._get_current_object() if current_user.is_authenticated else None,
        'create', 'order', order.id,
        f'Створено замовлення #{order.id} для {client.name or client.instagram or f"#{client.id}"}',
        after_data=_order_snapshot(order),
    )
    return order


def get_orders(q=None, phone=None, instagram=None, city=None, size=None, delivery_type=None, date_from=None, date_to=None, subscription_id=None):
    from app.models.subscription import Subscription as _Subscription
    query = Order.query.options(joinedload(Order.client)).join(Client)
    is_client_search = bool(q or phone or instagram)

    if subscription_id:
        query = query.filter(Order.subscription_id == subscription_id)
    elif not is_client_search:
        # Default: hide stopped-subscription orders, but keep already-delivered ones
        from app.extensions import db as _db
        not_stopped = ~_db.session.query(_Subscription.id).filter(
            _Subscription.id == Order.subscription_id,
            _Subscription.is_stopped.is_(True),
        ).correlate(Order).exists()
        has_delivered = _db.session.query(Delivery.id).filter(
            Delivery.order_id == Order.id,
            Delivery.status == 'Доставлено',
        ).correlate(Order).exists()
        has_individually_resumed = _db.session.query(Delivery.id).filter(
            Delivery.order_id == Order.id,
            Delivery.individually_resumed.is_(True),
        ).correlate(Order).exists()
        query = query.filter(or_(not_stopped, has_delivered, has_individually_resumed))
    # When searching by client: include all orders (stopped subscriptions visible with СТОП badge)
    if q:
        q_stripped = q.lstrip('@').lstrip('#')
        like_q = f'%{q}%'
        like_q_stripped = f'%{q_stripped}%'
        id_filter = None
        if q_stripped.isdigit():
            id_filter = Order.id == int(q_stripped)
        text_filters = or_(
            Client.instagram.ilike(like_q),
            Client.phone.ilike(like_q),
            Client.telegram.ilike(like_q),
            Client.telegram.ilike(like_q_stripped),
            Order.recipient_name.ilike(like_q),
            Order.recipient_phone.ilike(like_q),
            Order.recipient_social.ilike(like_q),
            Order.recipient_social.ilike(like_q_stripped),
            Order.city.ilike(like_q),
            Order.street.ilike(like_q),
        )
        query = query.filter(or_(id_filter, text_filters) if id_filter is not None else text_filters)
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
        query = query.join(Delivery, Delivery.order_id == Order.id)
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


def sync_order_to_active_deliveries(order):
    """Propagate order-level fields onto the order's non-finalized deliveries.

    Single choke point for the order → delivery fan-out, shared by update_order
    and update_subscription so no edit path can silently forget a field.
    Does NOT touch delivery_date — callers own their own date logic.
    """
    for delivery in order.deliveries:
        if delivery.status in ('Доставлено', 'Скасовано'):
            continue
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
        delivery.size = order.size
        delivery.bouquet_type = order.bouquet_type
        delivery.composition_type = order.composition_type
        delivery.time_from = order.time_from
        delivery.time_to = order.time_to


def update_order(order, form):
    before = _order_snapshot(order)
    new_client_id = form.get('client_id', '').strip()
    if new_client_id:
        try:
            new_client_id_int = int(new_client_id)
        except (ValueError, TypeError):
            new_client_id_int = None
        if new_client_id_int and new_client_id_int != order.client_id:
            new_client = Client.query.get(new_client_id_int)
            if not new_client:
                raise ValueError('Клієнта не знайдено!')
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
    earliest_active = min(
        active_deliveries, key=lambda d: d.delivery_date or datetime.date.min, default=None
    )
    if earliest_active is not None:
        earliest_active.delivery_date = delivery_date
    sync_order_to_active_deliveries(order)

    db.session.commit()

    from flask_login import current_user
    from app.services.activity_log_service import log as _log
    _log(
        current_user._get_current_object() if current_user.is_authenticated else None,
        'edit', 'order', order.id,
        f'Редаговано замовлення #{order.id}',
        before_data=before,
        after_data=_order_snapshot(order),
    )
    return order


def delete_order(order):
    logger.warning(f'Deleting order {order.id}')
    order_id = order.id
    before = _order_snapshot(order)
    client_label = order.client.name or order.client.instagram or f'#{order.client_id}' if order.client else ''

    from app.models.delivery_route import RouteDelivery
    for delivery in list(order.deliveries):
        RouteDelivery.query.filter_by(delivery_id=delivery.id).delete()
        db.session.delete(delivery)
    RecipientPhone.query.filter_by(order_id=order.id).delete()
    db.session.flush()
    db.session.delete(order)
    db.session.commit()

    from flask_login import current_user
    from app.services.activity_log_service import log as _log
    _log(
        current_user._get_current_object() if current_user.is_authenticated else None,
        'delete', 'order', order_id,
        f'Видалено замовлення #{order_id} ({client_label})',
        before_data=before,
    )
