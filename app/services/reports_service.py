from datetime import date, datetime, timedelta
from sqlalchemy import func, case, literal

from app.extensions import db
from app.models import Client, Order, Settings
from app.models.subscription import Subscription
from app.models.user import User


# ── Label normalization ────────────────────────────────────────────────────────

UNSPECIFIED_TOKENS = {
    '', '-', '—', 'none', 'null', 'n/a', 'na',
    'не вказано', 'невказано', 'не вказана', 'не вказаний', 'не має', 'немає',
}
UNSPECIFIED_CANONICAL = {'none', 'null', 'na', 'невказано', 'немає', 'нема'}


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


def _rows_to_items(rows):
    buckets = {}
    for raw_label, count in rows:
        key = _label_key(raw_label)
        if key not in buckets:
            buckets[key] = {'label': _display_label(raw_label), 'count': 0}
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
    for label, count in sorted(by_label.items(), key=lambda r: r[0].lower()):
        ordered.append({'label': label, 'count': count})
    return ordered


def _total(items):
    return sum(item['count'] for item in items)


# ── Date helpers ───────────────────────────────────────────────────────────────

def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return None


def _month_start(d):
    return date(d.year, d.month, 1)


def _next_month(d):
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _fill_monthly_gaps(month_counts):
    """Convert {date: count} → (labels, values) with zero-filled gaps."""
    if not month_counts:
        return [], []
    cursor = min(month_counts.keys())
    last = max(month_counts.keys())
    labels, values = [], []
    while cursor <= last:
        labels.append(cursor.strftime('%m.%Y'))
        values.append(month_counts.get(cursor, 0))
        cursor = _next_month(cursor)
    return labels, values


# ── Private helpers ────────────────────────────────────────────────────────────

def _monthly_orders_trend():
    """Last-365-days order & subscription counts grouped by month."""
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
    last_month = _month_start(datetime.utcnow().date())
    labels, orders_values, subscriptions_values = [], [], []
    cursor = first_month
    while cursor <= last_month:
        v = monthly.get(cursor, {'orders': 0, 'subscriptions': 0})
        labels.append(cursor.strftime('%m.%Y'))
        orders_values.append(v['orders'])
        subscriptions_values.append(v['subscriptions'])
        cursor = _next_month(cursor)

    return {'labels': labels, 'orders_values': orders_values, 'subscriptions_values': subscriptions_values}


# ── Public API ─────────────────────────────────────────────────────────────────
# Each function returns a flat dict scoped to its domain.
# Routes namespace them: orders=get_orders_data(...), deliveries=get_deliveries_analytics(...)
# Template accesses: {{ orders.marketing_all_total }}, {{ deliveries.total }}, etc.

_PL_TOP_N = 8


def get_orders_data(date_from_str=None, date_to_str=None):
    """Marketing, for-whom, delivery-type, size breakdowns + 365-day order trend."""
    d_from = _parse_date(date_from_str)
    d_to = _parse_date(date_to_str)
    has_range = bool(d_from or d_to)

    def _range_filters(col):
        f = []
        if d_from:
            f.append(col >= d_from)
        if d_to:
            f.append(col <= d_to)
        return f

    # Marketing source — all-time + selected range
    marketing_all_rows = (
        db.session.query(Client.marketing_source, func.count(Order.id))
        .join(Order, Order.client_id == Client.id)
        .group_by(Client.marketing_source)
        .all()
    )
    marketing_range_rows = (
        db.session.query(Client.marketing_source, func.count(Order.id))
        .join(Order, Order.client_id == Client.id)
        .filter(*_range_filters(Order.created_at))
        .group_by(Client.marketing_source)
        .all()
    ) if has_range else []

    # For whom — all-time + selected range
    for_whom_all_rows = (
        db.session.query(Order.for_whom, func.count(Order.id))
        .group_by(Order.for_whom)
        .all()
    )
    for_whom_range_rows = (
        db.session.query(Order.for_whom, func.count(Order.id))
        .filter(*_range_filters(Order.created_at))
        .group_by(Order.for_whom)
        .all()
    ) if has_range else []

    # Delivery type / size — always all-time (structural breakdown)
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
        s.value for s in Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    ]
    size_settings = [
        s.value for s in Settings.query.filter_by(type='size').order_by(Settings.value).all()
    ]

    marketing_all = _rows_to_items(marketing_all_rows)
    marketing_range = _rows_to_items(marketing_range_rows)
    for_whom_all = _rows_to_items(for_whom_all_rows)
    for_whom_range = _rows_to_items(for_whom_range_rows)
    delivery_type_all = _ordered_items(_rows_to_items(delivery_type_rows), delivery_type_settings)
    size_all = _ordered_items(_rows_to_items(size_rows), size_settings)

    trend = _monthly_orders_trend()

    return {
        'marketing_all': marketing_all,
        'marketing_range': marketing_range,
        'for_whom_all': for_whom_all,
        'for_whom_range': for_whom_range,
        'delivery_type_all': delivery_type_all,
        'size_all': size_all,
        'marketing_all_total': _total(marketing_all),
        'marketing_range_total': _total(marketing_range),
        'for_whom_all_total': _total(for_whom_all),
        'for_whom_range_total': _total(for_whom_range),
        'delivery_type_total': _total(delivery_type_all),
        'size_total': _total(size_all),
        'marketing_all_chart': _items_to_chart(marketing_all),
        'marketing_range_chart': _items_to_chart(marketing_range),
        'for_whom_all_chart': _items_to_chart(for_whom_all),
        'for_whom_range_chart': _items_to_chart(for_whom_range),
        'delivery_type_chart': _items_to_chart(delivery_type_all),
        'size_chart': _items_to_chart(size_all),
        'monthly_orders_total': sum(trend['orders_values']),
        'monthly_subscriptions_total': sum(trend['subscriptions_values']),
        'monthly_orders_trend_chart': trend,
    }


def get_deliveries_analytics(date_from_str=None, date_to_str=None):
    """Delivery KPIs: status counts (SQL aggregation), dynamics, city distribution."""
    from app.models.delivery import Delivery

    d_from = _parse_date(date_from_str)
    d_to = _parse_date(date_to_str)

    base = db.session.query(Delivery)
    if d_from:
        base = base.filter(Delivery.delivery_date >= d_from)
    if d_to:
        base = base.filter(Delivery.delivery_date <= d_to)

    # SQL aggregation — avoids loading full objects into memory
    status_row = base.with_entities(
        func.count(Delivery.id).label('total'),
        func.sum(case((Delivery.status == 'Доставлено', 1), else_=0)).label('completed'),
        func.sum(case((Delivery.status == 'Скасовано', 1), else_=0)).label('cancelled'),
    ).one()

    total = status_row.total or 0
    completed = status_row.completed or 0
    cancelled = status_row.cancelled or 0
    in_progress = total - completed - cancelled

    completed_pct = round(completed / total * 100, 1) if total else 0.0
    in_progress_pct = round(in_progress / total * 100, 1) if total else 0.0
    cancelled_pct = round(cancelled / total * 100, 1) if total else 0.0

    # % change vs previous period
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

    # Dynamics: fetch only delivery_date column, group in Python
    date_rows = base.with_entities(Delivery.delivery_date).all()
    monthly = {}
    for (d,) in date_rows:
        m = _month_start(d)
        monthly[m] = monthly.get(m, 0) + 1
    dyn_labels, dyn_values = _fill_monthly_gaps(monthly)

    # City distribution
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

    return {
        'total': total,
        'completed': completed,
        'in_progress': in_progress,
        'cancelled': cancelled,
        'completed_pct': completed_pct,
        'in_progress_pct': in_progress_pct,
        'cancelled_pct': cancelled_pct,
        'total_change_pct': total_change_pct,
        'dynamics_chart': {'labels': dyn_labels, 'values': dyn_values},
        'city_chart': _items_to_chart(_rows_to_items(city_rows)),
    }


def get_pl_data(date_from_str=None, date_to_str=None):
    """P&L: revenue, expenses, profit, margin, expense breakdown by category."""
    from app.models.transaction import Transaction
    from app.models.expense_category import ExpenseCategory

    d_from = _parse_date(date_from_str)
    d_to = _parse_date(date_to_str)

    def _date_filters(col):
        f = []
        if d_from:
            f.append(col >= d_from)
        if d_to:
            f.append(col <= d_to)
        return f

    revenue = (
        db.session.query(func.sum(Transaction.amount))
        .filter(Transaction.transaction_type == 'credit', *_date_filters(Transaction.date))
        .scalar() or 0
    )
    total_expenses = (
        db.session.query(func.sum(Transaction.amount))
        .filter(Transaction.transaction_type == 'debit', *_date_filters(Transaction.date))
        .scalar() or 0
    )
    profit = revenue - total_expenses
    margin = round(profit / revenue * 100, 1) if revenue else 0.0

    # Expense breakdown by category
    cat_rows = (
        db.session.query(ExpenseCategory.name, func.sum(Transaction.amount).label('total'))
        .join(Settings, Settings.id == Transaction.expense_type_id)
        .join(ExpenseCategory, ExpenseCategory.id == Settings.category_id)
        .filter(Transaction.transaction_type == 'debit', *_date_filters(Transaction.date))
        .group_by(ExpenseCategory.id, ExpenseCategory.name)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )
    uncategorized = (
        db.session.query(func.sum(Transaction.amount))
        .filter(
            Transaction.transaction_type == 'debit',
            Transaction.expense_type_id.is_(None),
            *_date_filters(Transaction.date),
        )
        .scalar() or 0
    )

    all_exp = [(name, int(total)) for name, total in cat_rows]
    if uncategorized:
        all_exp.append(('Без категорії', int(uncategorized)))
    all_exp.sort(key=lambda x: -x[1])

    expense_breakdown = []
    other_total = 0
    for i, (label, amount) in enumerate(all_exp):
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

    delivery_expenses = (
        db.session.query(func.sum(Transaction.amount))
        .join(Settings, Settings.id == Transaction.expense_type_id)
        .join(ExpenseCategory, ExpenseCategory.id == Settings.category_id)
        .filter(
            Transaction.transaction_type == 'debit',
            ExpenseCategory.slug == 'delivery',
            *_date_filters(Transaction.date),
        )
        .scalar() or 0
    )

    return {
        'revenue': revenue,
        'expenses': total_expenses,
        'profit': profit,
        'margin': margin,
        'expense_breakdown': expense_breakdown,
        'delivery_expenses': delivery_expenses,
    }


def get_subscription_renewal_rate(date_from_str=None, date_to_str=None):
    """Subscription renewal KPIs: rate, renewed/declined/pending counts."""
    from app.models.delivery import Delivery

    d_from = _parse_date(date_from_str)
    d_to = _parse_date(date_to_str)

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
            func.count(case((Subscription.followup_status == 'extended', Subscription.id))).label('renewed'),
            func.count(case((Subscription.followup_status == 'declined', Subscription.id))).label('declined'),
            func.count(case((Subscription.followup_status == 'pending', Subscription.id))).label('pending'),
        )
        .join(last_delivery_subq, last_delivery_subq.c.subscription_id == Subscription.id)
        .filter(Subscription.is_renewal_reminder == False)  # noqa: E712
    )

    if d_from:
        q = q.filter(last_delivery_subq.c.last_date >= d_from)
    if d_to:
        q = q.filter(last_delivery_subq.c.last_date <= d_to)
    else:
        q = q.filter(last_delivery_subq.c.last_date < date.today())

    row = q.one()
    total = row.total or 0
    renewed = row.renewed or 0
    declined = row.declined or 0
    pending = row.pending or 0
    renewal_rate = round(renewed / total * 100, 1) if total else 0.0

    return {
        'renewal_rate': renewal_rate,
        'renewed_count': renewed,
        'expired_count': total,
        'declined_count': declined,
        'pending_count': pending,
    }


def get_florist_sales_data(date_from_str=None, date_to_str=None):
    """Offline florist sales with 5% bonus. Defaults to current month when no range given."""
    from app.models.florist_sale import FloristSale

    d_from = _parse_date(date_from_str)
    d_to = _parse_date(date_to_str)

    if not d_from and not d_to:
        today = date.today()
        d_from = date(today.year, today.month, 1)
        d_to = _next_month(d_from) - timedelta(days=1)

    q = (
        db.session.query(
            User.username,
            func.count(FloristSale.id),
            func.sum(FloristSale.amount),
            func.sum(FloristSale.bonus_amount),
        )
        .join(User, User.id == FloristSale.florist_id)
    )
    if d_from:
        q = q.filter(func.date(FloristSale.created_at) >= d_from)
    if d_to:
        q = q.filter(func.date(FloristSale.created_at) <= d_to)

    rows = q.group_by(User.id, User.username).order_by(func.sum(FloristSale.amount).desc()).all()

    florist_rows = []
    grand_total = grand_bonus = 0.0
    grand_count = 0
    for username, count, total_amount, total_bonus in rows:
        t = float(total_amount or 0)
        b = float(total_bonus or 0)
        c = int(count or 0)
        florist_rows.append({'name': username, 'count': c, 'total_amount': t, 'total_bonus': b})
        grand_total += t
        grand_bonus += b
        grand_count += c

    return {
        'rows': florist_rows,
        'grand_total': grand_total,
        'grand_bonus': grand_bonus,
        'grand_count': grand_count,
    }
