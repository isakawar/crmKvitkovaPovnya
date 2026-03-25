from app.extensions import db
from app.models import Client, Order, Delivery
from app.models.subscription import Subscription
import datetime
import logging
from sqlalchemy import or_

logger = logging.getLogger(__name__)

SUBSCRIPTION_TYPES = ['Weekly', 'Monthly', 'Bi-weekly']
WEEKDAY_MAP = {'ПН': 0, 'ВТ': 1, 'СР': 2, 'ЧТ': 3, 'ПТ': 4, 'СБ': 5, 'НД': 6}
REVERSE_WEEKDAY_MAP = {v: k for k, v in WEEKDAY_MAP.items()}


def calculate_next_delivery_date(previous_date, subscription_type, desired_weekday):
    if subscription_type == 'Weekly':
        next_date = previous_date + datetime.timedelta(days=7)
        while next_date.weekday() != desired_weekday:
            next_date += datetime.timedelta(days=1)
        return next_date

    if subscription_type == 'Bi-weekly':
        next_date = previous_date + datetime.timedelta(days=14)
        while next_date.weekday() != desired_weekday:
            next_date += datetime.timedelta(days=1)
        return next_date

    if subscription_type == 'Monthly':
        base_date = previous_date + datetime.timedelta(days=28)
        days_forward = (desired_weekday - base_date.weekday()) % 7
        days_backward = (base_date.weekday() - desired_weekday) % 7
        if days_forward <= days_backward:
            return base_date + datetime.timedelta(days=days_forward)
        return base_date - datetime.timedelta(days=days_backward)

    return previous_date


def build_delivery_dates(first_date, subscription_type, delivery_day):
    dates = [first_date]
    desired_weekday = WEEKDAY_MAP.get(delivery_day, first_date.weekday())
    previous_date = first_date
    for _ in range(3):
        next_date = calculate_next_delivery_date(previous_date, subscription_type, desired_weekday)
        dates.append(next_date)
        previous_date = next_date
    return dates


def build_delivery_dates_n(first_date, subscription_type, delivery_day, n):
    """Like build_delivery_dates but generates exactly n dates."""
    if n <= 0:
        return []
    dates = [first_date]
    desired_weekday = WEEKDAY_MAP.get(delivery_day, first_date.weekday())
    previous_date = first_date
    for _ in range(n - 1):
        next_date = calculate_next_delivery_date(previous_date, subscription_type, desired_weekday)
        dates.append(next_date)
        previous_date = next_date
    return dates


def _create_delivery_for_order(order, client_id, is_first):
    return Delivery(
        order_id=order.id,
        client_id=client_id,
        delivery_date=order.delivery_date,
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


def create_subscription(client, form):
    logger.info(f'Creating subscription for client {client.id}')

    is_pickup = form.get('is_pickup') == 'on'
    sub_type = (form.get('delivery_type') or '').strip()
    delivery_day = (form.get('delivery_day') or '').strip()
    first_date = datetime.datetime.strptime(form['first_delivery_date'], '%Y-%m-%d').date()

    if not delivery_day:
        delivery_day = REVERSE_WEEKDAY_MAP.get(first_date.weekday(), 'ПН')

    custom_amount_raw = (form.get('custom_amount') or '').strip()
    custom_amount = int(custom_amount_raw) if custom_amount_raw else None

    subscription = Subscription(
        client_id=client.id,
        type=sub_type,
        status='active',
        delivery_day=delivery_day,
        time_from=form.get('time_from') or None,
        time_to=form.get('time_to') or None,
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
        bouquet_type=form.get('bouquet_type') or None,
        composition_type=form.get('composition_type') or None,
        for_whom=form.get('for_whom') or '',
        comment=form.get('comment') or None,
        preferences=form.get('preferences') or None,
    )
    db.session.add(subscription)
    db.session.flush()

    dates = build_delivery_dates(first_date, sub_type, delivery_day)
    first_order_id = None

    for i, d_date in enumerate(dates):
        order = Order(
            client_id=client.id,
            subscription_id=subscription.id,
            sequence_number=i + 1,
            recipient_name=subscription.recipient_name,
            recipient_phone=subscription.recipient_phone,
            recipient_social=subscription.recipient_social,
            city=subscription.city,
            street=subscription.street,
            building_number=subscription.building_number,
            floor=subscription.floor,
            entrance=subscription.entrance,
            is_pickup=subscription.is_pickup,
            address_comment=subscription.address_comment,
            delivery_method=subscription.delivery_method,
            size=subscription.size,
            custom_amount=subscription.custom_amount,
            delivery_date=d_date,
            time_from=subscription.time_from if i == 0 else None,
            time_to=subscription.time_to if i == 0 else None,
            bouquet_type=subscription.bouquet_type,
            composition_type=subscription.composition_type,
            for_whom=subscription.for_whom,
            comment=subscription.comment if i == 0 else None,
            preferences=subscription.preferences,
        )
        db.session.add(order)
        db.session.flush()

        if i == 0:
            first_order_id = order.id
            additional_phones = (
                form.getlist('additional_phones')
                if hasattr(form, 'getlist')
                else form.get('additional_phones', [])
            )
            from app.models.recipient_phone import RecipientPhone
            for j, ph in enumerate(additional_phones, start=1):
                if ph.strip():
                    db.session.add(RecipientPhone(order_id=order.id, phone=ph.strip(), position=j))

        delivery = _create_delivery_for_order(order, client.id, is_first=(i == 0))
        db.session.add(delivery)

    db.session.commit()
    return subscription


def create_subscription_from_import(client, form, delivery_number):
    """
    Create a subscription for import scenarios where delivery_number indicates
    which delivery in the cycle this is (1-5).

    delivery_number 1 → 4 deliveries (full cycle)
    delivery_number 2 → 3 deliveries
    delivery_number 3 → 2 deliveries
    delivery_number 4 → 1 delivery
    delivery_number 5 → 1 delivery + followup_status='pending'
    """
    logger.info(f'Creating import subscription for client {client.id}, delivery_number={delivery_number}')

    is_pickup = form.get('is_pickup') == 'on'
    sub_type = (form.get('delivery_type') or '').strip()
    delivery_day = (form.get('delivery_day') or '').strip()
    first_date = datetime.datetime.strptime(form['first_delivery_date'], '%Y-%m-%d').date()

    if not delivery_day:
        delivery_day = REVERSE_WEEKDAY_MAP.get(first_date.weekday(), 'ПН')

    custom_amount_raw = (form.get('custom_amount') or '').strip()
    custom_amount = int(custom_amount_raw) if custom_amount_raw else None

    is_wedding = form.get('is_wedding') in (True, 'true', 'True', '1', 'on')

    subscription = Subscription(
        client_id=client.id,
        type=sub_type,
        status='active',
        delivery_day=delivery_day,
        time_from=form.get('time_from') or None,
        time_to=form.get('time_to') or None,
        recipient_name=form.get('recipient_name') or '',
        recipient_phone=form.get('recipient_phone') or '',
        recipient_social=form.get('recipient_social') or None,
        city=form.get('city') or 'Київ',
        street='Самовивіз' if is_pickup else (form.get('street') or ''),
        building_number=form.get('building_number') or None,
        floor=form.get('floor') or None,
        entrance=form.get('entrance') or None,
        is_pickup=is_pickup,
        address_comment=form.get('address_comment') or None,
        delivery_method=form.get('delivery_method') or 'courier',
        size=form.get('size') or 'M',
        custom_amount=custom_amount,
        bouquet_type=form.get('bouquet_type') or None,
        composition_type=form.get('composition_type') or None,
        for_whom=form.get('for_whom') or '',
        comment=form.get('comment') or None,
        preferences=form.get('preferences') or None,
        is_wedding=is_wedding,
    )

    if delivery_number >= 5:
        subscription.is_renewal_reminder = True
        subscription.followup_status = 'pending'

    db.session.add(subscription)
    db.session.flush()

    if delivery_number >= 5:
        return subscription

    num_deliveries = max(1, 5 - delivery_number)
    dates = build_delivery_dates_n(first_date, sub_type, delivery_day, num_deliveries)

    for i, d_date in enumerate(dates):
        seq = delivery_number + i
        order = Order(
            client_id=client.id,
            subscription_id=subscription.id,
            sequence_number=seq,
            recipient_name=subscription.recipient_name,
            recipient_phone=subscription.recipient_phone,
            recipient_social=subscription.recipient_social,
            city=subscription.city,
            street=subscription.street,
            building_number=subscription.building_number,
            floor=subscription.floor,
            entrance=subscription.entrance,
            is_pickup=subscription.is_pickup,
            address_comment=subscription.address_comment,
            delivery_method=subscription.delivery_method,
            size=subscription.size,
            custom_amount=subscription.custom_amount,
            delivery_date=d_date,
            time_from=subscription.time_from if i == 0 else None,
            time_to=subscription.time_to if i == 0 else None,
            bouquet_type=subscription.bouquet_type,
            composition_type=subscription.composition_type,
            for_whom=subscription.for_whom,
            comment=subscription.comment if i == 0 else None,
            preferences=subscription.preferences,
        )
        db.session.add(order)
        db.session.flush()

        if i == 0:
            additional_phones = form.get('additional_phones', [])
            if isinstance(additional_phones, str):
                additional_phones = [additional_phones] if additional_phones else []
            from app.models.recipient_phone import RecipientPhone
            for j, ph in enumerate(additional_phones, start=1):
                if ph.strip():
                    db.session.add(RecipientPhone(order_id=order.id, phone=ph.strip(), position=j))

        delivery = _create_delivery_for_order(order, client.id, is_first=(i == 0))
        db.session.add(delivery)

    db.session.commit()
    return subscription


def extend_subscription(subscription):
    """Add another cycle of 4 orders/deliveries to the subscription."""
    last_order = (
        Order.query
        .filter_by(subscription_id=subscription.id)
        .order_by(Order.delivery_date.desc())
        .first()
    )
    if not last_order:
        raise ValueError('No orders found for subscription')

    last_delivery = (
        Delivery.query
        .filter_by(order_id=last_order.id)
        .order_by(Delivery.delivery_date.desc())
        .first()
    )
    last_date = last_delivery.delivery_date if last_delivery else last_order.delivery_date

    desired_weekday = WEEKDAY_MAP.get(subscription.delivery_day, last_date.weekday())
    first_next = calculate_next_delivery_date(last_date, subscription.type, desired_weekday)
    dates = build_delivery_dates(first_next, subscription.type, subscription.delivery_day)

    max_seq = (
        db.session.query(db.func.max(Order.sequence_number))
        .filter_by(subscription_id=subscription.id)
        .scalar()
    ) or 0

    for i, d_date in enumerate(dates):
        order = Order(
            client_id=subscription.client_id,
            subscription_id=subscription.id,
            sequence_number=max_seq + i + 1,
            recipient_name=subscription.recipient_name,
            recipient_phone=subscription.recipient_phone,
            recipient_social=subscription.recipient_social,
            city=subscription.city,
            street=subscription.street,
            building_number=subscription.building_number,
            floor=subscription.floor,
            entrance=subscription.entrance,
            is_pickup=subscription.is_pickup,
            address_comment=subscription.address_comment,
            delivery_method=subscription.delivery_method,
            size=subscription.size,
            custom_amount=subscription.custom_amount,
            delivery_date=d_date,
            time_from=subscription.time_from if i == 0 else None,
            time_to=subscription.time_to if i == 0 else None,
            bouquet_type=subscription.bouquet_type,
            composition_type=subscription.composition_type,
            for_whom=subscription.for_whom,
            comment=subscription.comment if i == 0 else None,
            preferences=subscription.preferences,
        )
        db.session.add(order)
        db.session.flush()

        delivery = _create_delivery_for_order(order, subscription.client_id, is_first=(i == 0))
        db.session.add(delivery)

    subscription.is_extended = True
    subscription.followup_status = 'extended'
    subscription.followup_at = datetime.datetime.utcnow()
    db.session.commit()
    return subscription


def delete_subscription(subscription):
    from app.models.delivery_route import RouteDelivery
    from app.models.recipient_phone import RecipientPhone

    for order in list(subscription.orders):
        for delivery in list(order.deliveries):
            RouteDelivery.query.filter_by(delivery_id=delivery.id).delete()
            db.session.delete(delivery)
        RecipientPhone.query.filter_by(order_id=order.id).delete()
        db.session.flush()
        db.session.delete(order)

    db.session.flush()
    db.session.delete(subscription)
    db.session.commit()


def get_subscriptions(q=None, city=None, sub_type=None):
    query = Subscription.query.join(Client)
    if q:
        like_q = f'%{q}%'
        query = query.filter(or_(
            Client.instagram.ilike(like_q),
            Client.phone.ilike(like_q),
            Subscription.recipient_name.ilike(like_q),
            Subscription.recipient_phone.ilike(like_q),
            Subscription.city.ilike(like_q),
        ))
    if city:
        query = query.filter(Subscription.city == city)
    if sub_type:
        query = query.filter(Subscription.type == sub_type)
    return query.order_by(Subscription.created_at.desc()).all()
