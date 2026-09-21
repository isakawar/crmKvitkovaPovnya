import datetime
import logging
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.constants import TXN_DELIVERY_CHARGE
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

    if order.discount is not None:
        discount = order.discount
    else:
        client = Client.query.get(order.client_id)
        discount = client.effective_discount if client else 0
    return int(base * (1 - discount / 100))


def resolve_charge_amount(order: Order) -> int | None:
    """Сума до списання за замовлення: спершу заморожена ціна, потім — жива.

    ``order.charged_amount`` фіксується при створенні/редагуванні замовлення та
    підписки (ціна за одну доставку, вже після ÷4 і знижки). Зміна цін в
    активному ``PricePreset`` не має заднім числом переоцінювати вже створені
    замовлення — підписки в тому числі. Тому ``get_order_price()`` наживо
    використовується лише як фолбек, коли знімка ціни немає.
    """
    if order.charged_amount is not None:
        return order.charged_amount
    return get_order_price(order)


def net_charged_for_delivery(delivery_id: int) -> Decimal:
    """Скільки зараз списано за доставку — СУМА, а не факт наявності транзакції.

    Сторно (``reverse_delivery_charge``) пишеться окремим рядком ``delivery_charge``
    з від'ємною сумою, щоб не ламати жоден звіт: усі вони підсумовують
    ``delivery_charge``, тож сторно занулюється саме там, де треба, без
    спеціального типу транзакції.

    Через це «чи списано за доставку» — це питання про НЕТТО-суму, а не про
    існування рядка: після сторно рядки є, але нетто == 0, і доставку можна
    списати знову, якщо її повторно проведуть як доставлену.
    """
    total = (
        db.session.query(func.sum(Transaction.amount))
        .filter(
            Transaction.delivery_id == delivery_id,
            Transaction.transaction_type == 'delivery_charge',
        )
        .scalar()
    )
    return Decimal(total or 0)


def charge_delivery(delivery: Delivery) -> Transaction | None:
    """Create a delivery_charge transaction for a completed delivery.

    Guard: if the delivery is already charged (net non-zero), skip.
    Updates client.credits and creates a Transaction record.
    Returns the created Transaction or None if skipped.
    """
    if net_charged_for_delivery(delivery.id) != 0:
        logger.debug('charge_delivery: delivery %d already charged, skipping', delivery.id)
        return None

    order = Order.query.get(delivery.order_id)
    if not order:
        logger.warning('charge_delivery: no order for delivery %d', delivery.id)
        return None

    amount = resolve_charge_amount(order)
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


def reverse_delivery_charge(delivery: Delivery) -> Transaction | None:
    """Сторнувати списання за доставку, яку перестали вважати доставленою.

    Списання за доставку раніше було однобічним: статус «Доставлено» знімав гроші
    з балансу, а повернення в «Скасовано»/«Очікує» їх не повертало. Оскільки
    статус міняє кур'єр із телеграм-бота, помилковий тап цілком реальний, і
    баланс клієнта лишався зміщеним назавжди.

    Сторно — окремий рядок ``delivery_charge`` з від'ємною сумою, **поточною
    датою**: закритий місяць не переписується заднім числом, а виправлення видно
    там, де його зробили. Оригінальний рядок лишається на місці, тож історія
    списань читається як є.

    Ідемпотентна: якщо нетто вже 0 (не списували або вже сторнували) — no-op.
    Повертає створену транзакцію або None.
    """
    net = net_charged_for_delivery(delivery.id)
    if net == 0:
        logger.debug('reverse_delivery_charge: delivery %d has nothing to reverse', delivery.id)
        return None

    client_id = delivery.order.client_id if delivery.order else delivery.client_id
    client = Client.query.get(client_id) if client_id else None
    if not client:
        logger.warning('reverse_delivery_charge: no client for delivery %d', delivery.id)
        return None

    txn = Transaction(
        transaction_type=TXN_DELIVERY_CHARGE,
        client_id=client.id,
        delivery_id=delivery.id,
        amount=-net,
        date=datetime.date.today(),
        comment=f'Сторно списання за доставку #{delivery.id}',
    )
    db.session.add(txn)
    client.credits = (client.credits or 0) + net
    logger.info('reverse_delivery_charge: delivery %d → client %d refunded %s',
                delivery.id, client.id, net)
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

    # Нетто, а не просто наявність рядка: у доставки зі сторно транзакції є, але
    # нетто == 0, тобто вона фактично не списана і має потрапити в добірку.
    charged_delivery_ids = {
        delivery_id for delivery_id, net in
        db.session.query(Transaction.delivery_id, func.sum(Transaction.amount))
        .filter(
            Transaction.transaction_type == 'delivery_charge',
            Transaction.delivery_id.isnot(None),
        )
        .group_by(Transaction.delivery_id)
        .all()
        if net
    }

    to_charge = [d for d in completed_deliveries if d.id not in charged_delivery_ids]

    total_amount = 0
    skipped_no_price = 0
    processed = 0

    for delivery in to_charge:
        order = Order.query.get(delivery.order_id)
        if not order:
            continue

        amount = resolve_charge_amount(order)
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
        .join(Delivery, Transaction.delivery_id == Delivery.id)
        .join(Order, Delivery.order_id == Order.id)
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
        rows.append({
            'id': txn.id,
            'date': txn.date,
            'client_id': txn.client_id,
            'client_name': client_name,
            'order_id': order.id,
            'delivery_id': delivery.id,
            'amount': txn.amount,
            'discount': order.discount or 0,
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
