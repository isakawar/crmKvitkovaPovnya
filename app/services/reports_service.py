from datetime import date, datetime, timedelta
from sqlalchemy import func, case, literal

from app.extensions import db
from app.models import Client, Order, Settings
from app.models.subscription import Subscription
from app.models.user import User


UNSPECIFIED_TOKENS = {
    '',
    '-',
    '—',
    'none',
    'null',
    'n/a',
    'na',
    'не вказано',
    'невказано',
    'не вказана',
    'не вказаний',
    'не має',
    'немає',
}

UNSPECIFIED_CANONICAL = {
    'none',
    'null',
    'na',
    'невказано',
    'немає',
    'нема',
}

def _compact(raw_value):
    return ' '.join((raw_value or '').strip().split())


def _label_key(raw_value):
    compact = _compact(raw_value)
    lowered = compact.lower()
    canonical = ''.join(ch for ch in lowered if ch.isalnum())
    if lowered in UNSPECIFIED_TOKENS or canonical in UNSPECIFIED_CANONICAL:
        return '__unspecified__'
    return lowered


def _display_label(raw_value):
    compact = _compact(raw_value)
    if _label_key(raw_value) == '__unspecified__':
        return 'Не вказано'
    return compact


def _parse_month(month_raw):
    today = datetime.utcnow().date()
    default_month = date(today.year, today.month, 1)
    if not month_raw:
        return default_month
    try:
        parsed = datetime.strptime(month_raw, '%Y-%m').date()
        return date(parsed.year, parsed.month, 1)
    except ValueError:
        return default_month


def _month_bounds(month_start):
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    start_dt = datetime.combine(month_start, datetime.min.time())
    end_dt = datetime.combine(next_month, datetime.min.time())
    return start_dt, end_dt


def _rows_to_items(rows):
    buckets = {}
    for raw_label, count in rows:
        key = _label_key(raw_label)
        if key not in buckets:
            buckets[key] = {
                'label': _display_label(raw_label),
                'count': 0,
            }
        buckets[key]['count'] += int(count or 0)

    items = list(buckets.values())
    items.sort(key=lambda row: (-row['count'], row['label'].lower()))
    return items


def _items_to_chart(items):
    return {
        'labels': [item['label'] for item in items],
        'values': [item['count'] for item in items],
    }


def _ordered_items(items, preferred_labels):
    by_label = {item['label']: item['count'] for item in items}
    ordered = []

    for label in preferred_labels:
        if label in by_label:
            ordered.append({'label': label, 'count': by_label.pop(label)})

    extras = sorted(by_label.items(), key=lambda row: row[0].lower())
    for label, count in extras:
        ordered.append({'label': label, 'count': count})
    return ordered


def _total(items):
    return sum(item['count'] for item in items)


def _month_start(d):
    return date(d.year, d.month, 1)


def _next_month(d):
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _monthly_orders_trend():
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=365)
    rows = (
        db.session.query(Order.created_at, Order.subscription_id)
        .filter(Order.created_at.isnot(None), Order.created_at >= cutoff)
        .order_by(Order.created_at.asc())
        .all()
    )
    if not rows:
        return {'labels': [], 'orders_values': [], 'subscriptions_values': []}

    monthly = {}
    for created_at, subscription_id in rows:
        month = _month_start(created_at.date())
        bucket = monthly.setdefault(month, {'orders': 0, 'subscriptions': 0})
        bucket['orders'] += 1
        if subscription_id is not None:
            bucket['subscriptions'] += 1

    first_month = min(monthly.keys())
    today = datetime.utcnow().date()
    last_month = _month_start(today)

    labels = []
    orders_values = []
    subscriptions_values = []

    cursor = first_month
    while cursor <= last_month:
        values = monthly.get(cursor, {'orders': 0, 'subscriptions': 0})
        labels.append(cursor.strftime('%m.%Y'))
        orders_values.append(values['orders'])
        subscriptions_values.append(values['subscriptions'])
        cursor = _next_month(cursor)

    return {
        'labels': labels,
        'orders_values': orders_values,
        'subscriptions_values': subscriptions_values,
    }


def get_reports_data(selected_month_raw=None):
    month_start = _parse_month(selected_month_raw)
    month_start_dt, month_end_dt = _month_bounds(month_start)
    monthly_orders_trend_chart = _monthly_orders_trend()

    marketing_all_rows = (
        db.session.query(Client.marketing_source, func.count(Order.id))
        .join(Order, Order.client_id == Client.id)
        .group_by(Client.marketing_source)
        .all()
    )
    marketing_month_rows = (
        db.session.query(Client.marketing_source, func.count(Order.id))
        .join(Order, Order.client_id == Client.id)
        .filter(Order.created_at >= month_start_dt, Order.created_at < month_end_dt)
        .group_by(Client.marketing_source)
        .all()
    )

    for_whom_all_rows = (
        db.session.query(Order.for_whom, func.count(Order.id))
        .group_by(Order.for_whom)
        .all()
    )
    for_whom_month_rows = (
        db.session.query(Order.for_whom, func.count(Order.id))
        .filter(Order.created_at >= month_start_dt, Order.created_at < month_end_dt)
        .group_by(Order.for_whom)
        .all()
    )

    sub_type_expr = case(
        (Order.subscription_id.isnot(None), Subscription.type),
        else_=literal('One-time')
    )
    delivery_type_rows = (
        db.session.query(sub_type_expr, func.count(Order.id))
        .outerjoin(Subscription, Subscription.id == Order.subscription_id)
        .group_by(sub_type_expr)
        .all()
    )
    size_rows = (
        db.session.query(Order.size, func.count(Order.id))
        .group_by(Order.size)
        .all()
    )

    delivery_type_settings = [
        setting.value
        for setting in Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    ]
    size_settings = [
        setting.value
        for setting in Settings.query.filter_by(type='size').order_by(Settings.value).all()
    ]

    marketing_all = _rows_to_items(marketing_all_rows)
    marketing_month = _rows_to_items(marketing_month_rows)
    for_whom_all = _rows_to_items(for_whom_all_rows)
    for_whom_month = _rows_to_items(for_whom_month_rows)
    delivery_type_all = _ordered_items(_rows_to_items(delivery_type_rows), delivery_type_settings)
    size_all = _ordered_items(_rows_to_items(size_rows), size_settings)

    return {
        'selected_month': month_start.strftime('%Y-%m'),
        'selected_month_label': month_start.strftime('%m.%Y'),
        'marketing_all': marketing_all,
        'marketing_month': marketing_month,
        'for_whom_all': for_whom_all,
        'for_whom_month': for_whom_month,
        'delivery_type_all': delivery_type_all,
        'size_all': size_all,
        'marketing_all_total': _total(marketing_all),
        'marketing_month_total': _total(marketing_month),
        'for_whom_all_total': _total(for_whom_all),
        'for_whom_month_total': _total(for_whom_month),
        'delivery_type_total': _total(delivery_type_all),
        'size_total': _total(size_all),
        'monthly_orders_total': sum(monthly_orders_trend_chart['orders_values']),
        'monthly_subscriptions_total': sum(monthly_orders_trend_chart['subscriptions_values']),
        'marketing_all_chart': _items_to_chart(marketing_all),
        'marketing_month_chart': _items_to_chart(marketing_month),
        'for_whom_all_chart': _items_to_chart(for_whom_all),
        'for_whom_month_chart': _items_to_chart(for_whom_month),
        'delivery_type_chart': _items_to_chart(delivery_type_all),
        'size_chart': _items_to_chart(size_all),
        'monthly_orders_trend_chart': monthly_orders_trend_chart,
    }


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return None


def get_deliveries_analytics(date_from_str=None, date_to_str=None):
    from app.models.delivery import Delivery

    d_from = _parse_date(date_from_str)
    d_to = _parse_date(date_to_str)

    base = db.session.query(Delivery)
    if d_from:
        base = base.filter(Delivery.delivery_date >= d_from)
    if d_to:
        base = base.filter(Delivery.delivery_date <= d_to)

    deliveries = base.all()

    total = len(deliveries)
    completed = sum(1 for d in deliveries if d.status == 'Доставлено')
    cancelled = sum(1 for d in deliveries if d.status == 'Скасовано')
    in_progress = total - completed - cancelled

    completed_pct = round(completed / total * 100, 1) if total else 0.0
    in_progress_pct = round(in_progress / total * 100, 1) if total else 0.0
    cancelled_pct = round(cancelled / total * 100, 1) if total else 0.0

    # % change vs previous period (only when date range is set)
    total_change_pct = None
    if d_from and d_to:
        duration = (d_to - d_from).days + 1
        prev_to = d_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=duration - 1)
        prev_total = db.session.query(func.count(Delivery.id)).filter(
            Delivery.delivery_date >= prev_from,
            Delivery.delivery_date <= prev_to,
        ).scalar() or 0
        if prev_total > 0:
            total_change_pct = round((total - prev_total) / prev_total * 100, 1)

    # Dynamics by month (fill gaps between first and last month)
    monthly = {}
    for d in deliveries:
        m = _month_start(d.delivery_date)
        monthly[m] = monthly.get(m, 0) + 1

    if monthly:
        cursor = min(monthly.keys())
        last = max(monthly.keys())
        dyn_labels, dyn_values = [], []
        while cursor <= last:
            dyn_labels.append(cursor.strftime('%m.%Y'))
            dyn_values.append(monthly.get(cursor, 0))
            cursor = _next_month(cursor)
    else:
        dyn_labels, dyn_values = [], []

    # City distribution via Order.city join
    city_q = (
        db.session.query(Order.city, func.count(Delivery.id))
        .join(Order, Order.id == Delivery.order_id)
    )
    if d_from:
        city_q = city_q.filter(Delivery.delivery_date >= d_from)
    if d_to:
        city_q = city_q.filter(Delivery.delivery_date <= d_to)
    city_rows = (
        city_q.group_by(Order.city)
        .order_by(func.count(Delivery.id).desc())
        .limit(10)
        .all()
    )
    city_items = _rows_to_items(city_rows)

    return {
        'deliveries_total': total,
        'deliveries_completed': completed,
        'deliveries_in_progress': in_progress,
        'deliveries_cancelled': cancelled,
        'deliveries_completed_pct': completed_pct,
        'deliveries_in_progress_pct': in_progress_pct,
        'deliveries_cancelled_pct': cancelled_pct,
        'deliveries_total_change_pct': total_change_pct,
        'deliveries_dynamics_chart': {'labels': dyn_labels, 'values': dyn_values},
        'deliveries_city_chart': _items_to_chart(city_items),
    }


_DELIVERY_EXPENSE_TYPES = {'Доставка', 'Доставка квітів', 'Нова пошта'}
_PL_TOP_N = 8


def get_pl_data(date_from_str=None, date_to_str=None):
    from app.models.transaction import Transaction

    d_from = _parse_date(date_from_str)
    d_to = _parse_date(date_to_str)

    q = db.session.query(Transaction)
    if d_from:
        q = q.filter(Transaction.date >= d_from)
    if d_to:
        q = q.filter(Transaction.date <= d_to)
    transactions = q.all()

    revenue = sum(t.amount for t in transactions if t.transaction_type == 'credit')
    total_expenses = sum(t.amount for t in transactions if t.transaction_type == 'debit')
    profit = revenue - total_expenses
    margin = round(profit / revenue * 100, 1) if revenue else 0.0

    # Expense breakdown grouped by expense_type
    buckets = {}
    for t in transactions:
        if t.transaction_type != 'debit':
            continue
        key = (t.expense_type or '').strip() or 'Не вказано'
        buckets[key] = buckets.get(key, 0) + t.amount

    sorted_exp = sorted(buckets.items(), key=lambda x: -x[1])
    expense_breakdown = []
    other_total = 0
    for i, (label, amount) in enumerate(sorted_exp):
        pct = round(amount / total_expenses * 100, 1) if total_expenses else 0.0
        if i < _PL_TOP_N:
            expense_breakdown.append({'label': label, 'amount': amount, 'pct': pct})
        else:
            other_total += amount
    if other_total:
        expense_breakdown.append({
            'label': 'Інше',
            'amount': other_total,
            'pct': round(other_total / total_expenses * 100, 1) if total_expenses else 0.0,
        })

    # Delivery-related expenses for "Вартість доставки" KPI
    delivery_expenses = sum(
        t.amount for t in transactions
        if t.transaction_type == 'debit' and (t.expense_type or '') in _DELIVERY_EXPENSE_TYPES
    )

    return {
        'pl_revenue': revenue,
        'pl_expenses': total_expenses,
        'pl_profit': profit,
        'pl_margin': margin,
        'pl_expense_breakdown': expense_breakdown,
        'pl_delivery_expenses': delivery_expenses,
    }


def get_subscription_renewal_rate(date_from_str=None, date_to_str=None):
    from app.models.delivery import Delivery

    d_from = _parse_date(date_from_str)
    d_to = _parse_date(date_to_str)

    # MAX(delivery_date) per subscription
    last_delivery_subq = (
        db.session.query(
            Order.subscription_id,
            func.max(Delivery.delivery_date).label('last_date'),
        )
        .join(Delivery, Delivery.order_id == Order.id)
        .filter(Order.subscription_id.isnot(None))
        .group_by(Order.subscription_id)
        .subquery()
    )

    q = (
        db.session.query(
            func.count(Subscription.id).label('total'),
            func.count(
                case((Subscription.followup_status == 'extended', Subscription.id))
            ).label('renewed'),
            func.count(
                case((Subscription.followup_status == 'declined', Subscription.id))
            ).label('declined'),
            func.count(
                case((Subscription.followup_status == 'pending', Subscription.id))
            ).label('pending'),
        )
        .join(last_delivery_subq, last_delivery_subq.c.subscription_id == Subscription.id)
        .filter(Subscription.is_renewal_reminder == False)  # noqa: E712
    )

    if d_from:
        q = q.filter(last_delivery_subq.c.last_date >= d_from)
    if d_to:
        q = q.filter(last_delivery_subq.c.last_date <= d_to)
    else:
        # only subscriptions whose last delivery is already in the past
        q = q.filter(last_delivery_subq.c.last_date < date.today())

    row = q.one()
    total   = row.total   or 0
    renewed = row.renewed or 0
    declined = row.declined or 0
    pending  = row.pending  or 0
    renewal_rate = round(renewed / total * 100, 1) if total else 0.0

    return {
        'sub_renewal_rate':    renewal_rate,
        'sub_renewed_count':   renewed,
        'sub_expired_count':   total,
        'sub_declined_count':  declined,
        'sub_pending_count':   pending,
    }


def get_florist_sales_data(selected_month_raw=None):
    from app.models.florist_sale import FloristSale

    month_start = _parse_month(selected_month_raw)
    month_start_dt, month_end_dt = _month_bounds(month_start)

    rows = (
        db.session.query(
            User.username,
            func.count(FloristSale.id),
            func.sum(FloristSale.amount),
            func.sum(FloristSale.bonus_amount),
        )
        .join(User, User.id == FloristSale.florist_id)
        .filter(
            FloristSale.created_at >= month_start_dt,
            FloristSale.created_at < month_end_dt,
        )
        .group_by(User.id, User.username)
        .order_by(func.sum(FloristSale.amount).desc())
        .all()
    )

    florist_rows = []
    grand_total = 0.0
    grand_bonus = 0.0
    grand_count = 0

    for username, count, total_amount, total_bonus in rows:
        t = float(total_amount or 0)
        b = float(total_bonus or 0)
        c = int(count or 0)
        florist_rows.append({
            'name': username,
            'count': c,
            'total_amount': t,
            'total_bonus': b,
        })
        grand_total += t
        grand_bonus += b
        grand_count += c

    return {
        'florist_sales_rows': florist_rows,
        'florist_sales_grand_total': grand_total,
        'florist_sales_grand_bonus': grand_bonus,
        'florist_sales_grand_count': grand_count,
    }
