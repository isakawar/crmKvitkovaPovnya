import datetime
import logging

from app.extensions import db
from app.models import Order, Delivery
from app.models.client import Client
from app.models.price import Price
from app.models.price_preset import PricePreset
from app.models.settings import Settings
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)


def get_order_price(order: Order) -> int | None:
    """Return the charged amount for an order: price from active PricePreset after discount.

    For 'Власний' size: returns order.custom_amount (no price table lookup).
    For subscription orders: looks up Price(preset, 'subscription', size).
    For one-time orders: looks up Price(preset, 'one_time', size).
    Returns None if no active preset or no price entry found.
    """
    if order.size == 'Власний':
        base = order.custom_amount or 0
    else:
        preset = PricePreset.query.filter_by(is_active=True).first()
        if not preset:
            return None

        size_setting = Settings.query.filter_by(type='size', value=order.size).first()
        if not size_setting:
            return None

        order_type = 'subscription' if order.subscription_id else 'one_time'

        price_entry = Price.query.filter_by(
            preset_id=preset.id,
            order_type=order_type,
            size_id=size_setting.id,
        ).first()
        if not price_entry:
            return None
        base = price_entry.price
        if order.subscription_id:
            base = base / 4

    discount = order.discount or 0
    return int(base * (1 - discount / 100))


def charge_delivery(delivery: Delivery) -> Transaction | None:
    """Create a delivery_charge transaction for a completed delivery.

    Guard: if a delivery_charge already exists for this delivery, skip.
    Updates client.credits and creates a Transaction record.
    Returns the created Transaction or None if skipped.
    """
    existing = Transaction.query.filter_by(
        delivery_id=delivery.id,
        transaction_type='delivery_charge',
    ).first()
    if existing:
        logger.debug('charge_delivery: delivery %d already charged, skipping', delivery.id)
        return None

    order = Order.query.get(delivery.order_id)
    if not order:
        logger.warning('charge_delivery: no order for delivery %d', delivery.id)
        return None

    if order.subscription_id:
        amount = get_order_price(order)
    else:
        amount = order.charged_amount
        if amount is None:
            amount = get_order_price(order)
    if amount is None:
        logger.warning('charge_delivery: no price found for order %d (delivery %d)', order.id, delivery.id)
        return None
    if amount <= 0:
        return None

    client = Client.query.get(order.client_id)
    if not client:
        return None

    txn = Transaction(
        transaction_type='delivery_charge',
        client_id=client.id,
        delivery_id=delivery.id,
        amount=amount,
        date=delivery.delivery_date or datetime.date.today(),
        comment=f'Списання за доставку #{delivery.id}',
    )
    db.session.add(txn)
    client.credits = (client.credits or 0) - amount
    logger.info('charge_delivery: delivery %d → client %d charged %d', delivery.id, client.id, amount)
    return txn


def reconcile_historical_charges(dry_run: bool = True) -> dict:
    """Backfill delivery_charge transactions for all past completed deliveries.

    dry_run=True: calculate totals only, make no changes.
    dry_run=False: create transactions and update client.credits.

    Returns a summary dict with counts and total amounts.
    """
    completed_deliveries = (
        Delivery.query
        .filter(Delivery.status == 'Доставлено')
        .all()
    )

    charged_delivery_ids = {
        row[0] for row in
        db.session.query(Transaction.delivery_id)
        .filter(
            Transaction.transaction_type == 'delivery_charge',
            Transaction.delivery_id.isnot(None),
        )
        .all()
    }

    to_charge = [d for d in completed_deliveries if d.id not in charged_delivery_ids]

    total_amount = 0
    skipped_no_price = 0
    processed = 0

    for delivery in to_charge:
        order = Order.query.get(delivery.order_id)
        if not order:
            continue

        if order.subscription_id:
            amount = get_order_price(order)
        else:
            amount = order.charged_amount
            if amount is None:
                amount = get_order_price(order)
        if amount is None or amount <= 0:
            skipped_no_price += 1
            continue

        total_amount += amount
        processed += 1

        if not dry_run:
            charge_delivery(delivery)

    if not dry_run:
        db.session.commit()

    return {
        'dry_run': dry_run,
        'total_completed_deliveries': len(completed_deliveries),
        'already_charged': len(charged_delivery_ids),
        'to_process': len(to_charge),
        'processed': processed,
        'skipped_no_price': skipped_no_price,
        'total_amount': total_amount,
    }


def get_charges_data(
    date_from_str: str | None,
    date_to_str: str | None,
    client_search: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """Return delivery_charge transactions with client, order and discount info.

    Returns:
        rows: list of dicts for the current page
        total_amount: sum across the full filtered set (all pages)
        count: total records in the filtered set
        page, pages, per_page: pagination metadata
    """
    from sqlalchemy import or_, func

    date_from = None
    date_to = None
    try:
        if date_from_str:
            date_from = datetime.date.fromisoformat(date_from_str)
        if date_to_str:
            date_to = datetime.date.fromisoformat(date_to_str)
    except ValueError:
        pass

    base_query = (
        db.session.query(Transaction, Delivery, Order, Client)
        .outerjoin(Delivery, Transaction.delivery_id == Delivery.id)
        .outerjoin(Order, Delivery.order_id == Order.id)
        .outerjoin(Client, Transaction.client_id == Client.id)
        .filter(Transaction.transaction_type == 'delivery_charge')
    )
    if date_from:
        base_query = base_query.filter(Transaction.date >= date_from)
    if date_to:
        base_query = base_query.filter(Transaction.date <= date_to)
    if client_search:
        like_q = f'%{client_search.strip()}%'
        base_query = base_query.filter(
            or_(
                Client.name.ilike(like_q),
                Client.instagram.ilike(like_q),
                Client.telegram.ilike(like_q),
                Client.phone.contains(client_search.strip()),
            )
        )

    all_amounts = base_query.with_entities(Transaction.amount).all()
    total_amount_row = sum(r.amount for r in all_amounts)
    count = len(all_amounts)

    ordered = base_query.order_by(Transaction.date.desc(), Transaction.id.desc())
    page = max(1, page)
    pages = max(1, (count + per_page - 1) // per_page)
    page = min(page, pages)
    paginated = ordered.offset((page - 1) * per_page).limit(per_page).all()

    rows = []
    for txn, delivery, order, client in paginated:
        client_name = client.display_name if client else '—'
        is_adjustment = delivery is None
        rows.append({
            'id': txn.id,
            'date': txn.date,
            'client_id': txn.client_id,
            'client_name': client_name,
            'order_id': order.id if order else None,
            'delivery_id': delivery.id if delivery else None,
            'amount': txn.amount,
            'discount': order.discount if order else 0,
            'comment': txn.comment or '—',
            'is_adjustment': is_adjustment,
        })

    return {
        'rows': rows,
        'total_amount': total_amount_row,
        'count': count,
        'page': page,
        'pages': pages,
        'per_page': per_page,
        'date_from': date_from,
        'date_to': date_to,
    }
