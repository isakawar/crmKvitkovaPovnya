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


def _build_date_filters(col, d_from, d_to):
    f = []
    if d_from:
        f.append(col >= d_from)
    if d_to:
        f.append(col <= d_to)
    return f


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
    """Last-365-days trend: one-time orders and new subscriptions grouped by month."""
    cutoff = datetime.utcnow() - timedelta(days=365)

    order_rows = (
        db.session.query(
            func.extract('year', Order.created_at).label('y'),
            func.extract('month', Order.created_at).label('m'),
            func.count(Order.id).label('cnt'),
        )
        .filter(Order.subscription_id.is_(None), Order.created_at >= cutoff)
        .group_by('y', 'm')
        .all()
    )
    sub_rows = (
        db.session.query(
            func.extract('year', Subscription.created_at).label('y'),
            func.extract('month', Subscription.created_at).label('m'),
            func.count(Subscription.id).label('cnt'),
        )
        .filter(Subscription.created_at.isnot(None), Subscription.created_at >= cutoff)
        .group_by('y', 'm')
        .all()
    )

    if not order_rows and not sub_rows:
        return {'labels': [], 'orders_values': [], 'subscriptions_values': []}

    monthly = {}
    for r in order_rows:
        monthly.setdefault(date(int(r.y), int(r.m), 1), {'orders': 0, 'subscriptions': 0})['orders'] = int(r.cnt)
    for r in sub_rows:
        monthly.setdefault(date(int(r.y), int(r.m), 1), {'orders': 0, 'subscriptions': 0})['subscriptions'] = int(r.cnt)

    if not monthly:
        return {'labels': [], 'orders_values': [], 'subscriptions_values': []}

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

def get_orders_data(date_from_str=None, date_to_str=None):
    """Marketing, for-whom, delivery-type, size breakdowns + 365-day order trend."""
    d_from = _parse_date(date_from_str)
    d_to = _parse_date(date_to_str)
    has_range = bool(d_from or d_to)
    range_filters = _build_date_filters(Order.created_at, d_from, d_to)

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
        .filter(*range_filters)
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
        .filter(*range_filters)
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
        s.value for s in Settings.query.filter_by(type='size').order_by(Settings.sort_order.nullslast(), Settings.value).all()
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

    # Dynamics: aggregate monthly counts in SQL
    monthly_rows = (
        base.with_entities(
            func.extract('year', Delivery.delivery_date).label('y'),
            func.extract('month', Delivery.delivery_date).label('m'),
            func.count(Delivery.id).label('cnt'),
        )
        .group_by('y', 'm')
        .all()
    )
    monthly = {date(int(r.y), int(r.m), 1): int(r.cnt) for r in monthly_rows}
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


def _build_expense_breakdown(d_from, d_to, total_expenses):
    """Expense breakdown by category → subcategory. Uses 2 queries instead of N+1."""
    from app.models.transaction import Transaction
    from app.models.expense_category import ExpenseCategory

    date_filters = _build_date_filters(Transaction.date, d_from, d_to)

    # Single query: all categories with their child types and amounts
    type_rows = (
        db.session.query(
            ExpenseCategory.id.label('cat_id'),
            ExpenseCategory.name.label('cat_name'),
            Settings.value.label('type_name'),
            func.sum(Transaction.amount).label('type_total'),
        )
        .join(Settings, Settings.id == Transaction.expense_type_id)
        .join(ExpenseCategory, ExpenseCategory.id == Settings.category_id)
        .filter(Transaction.transaction_type == 'debit', *date_filters)
        .group_by(ExpenseCategory.id, ExpenseCategory.name, Settings.id, Settings.value)
        .order_by(ExpenseCategory.id, func.sum(Transaction.amount).desc())
        .all()
    )

    cats = {}
    for row in type_rows:
        if row.cat_id not in cats:
            cats[row.cat_id] = {'label': row.cat_name, 'total': 0, 'children': []}
        child_amount = int(row.type_total)
        cats[row.cat_id]['total'] += child_amount
        cats[row.cat_id]['children'].append({
            'label': row.type_name or 'Без назви',
            'amount': child_amount,
            'pct': round(child_amount / total_expenses * 100, 1) if total_expenses else 0.0,
        })

    breakdown = []
    for cat in cats.values():
        amount = cat['total']
        breakdown.append({
            'label': cat['label'],
            'amount': amount,
            'pct': round(amount / total_expenses * 100, 1) if total_expenses else 0.0,
            'is_group': True,
            'children': cat['children'],
        })

    # Uncategorized: types with no category
    uncat_rows = (
        db.session.query(Settings.value, func.sum(Transaction.amount).label('total'))
        .join(Transaction, Transaction.expense_type_id == Settings.id)
        .filter(Transaction.transaction_type == 'debit', Settings.category_id.is_(None), *date_filters)
        .group_by(Settings.id, Settings.value)
        .all()
    )
    for val, total in uncat_rows:
        amount = int(total)
        breakdown.append({
            'label': val or 'Без назви',
            'amount': amount,
            'pct': round(amount / total_expenses * 100, 1) if total_expenses else 0.0,
            'is_group': False,
            'children': [],
        })

    # Transactions with no expense_type_id at all
    no_type = (
        db.session.query(func.sum(Transaction.amount))
        .filter(Transaction.transaction_type == 'debit', Transaction.expense_type_id.is_(None), *date_filters)
        .scalar() or 0
    )
    if no_type:
        amount = int(no_type)
        breakdown.append({
            'label': 'Без категорії',
            'amount': amount,
            'pct': round(amount / total_expenses * 100, 1) if total_expenses else 0.0,
            'is_group': False,
            'children': [],
        })

    breakdown.sort(key=lambda x: -x['amount'])
    return breakdown


def get_pl_data(date_from_str=None, date_to_str=None):
    """P&L: revenue, expenses, profit, margin, expense breakdown by category."""
    from app.models.transaction import Transaction
    from app.models.expense_category import ExpenseCategory
    from app.models.delivery import Delivery

    d_from = _parse_date(date_from_str)
    d_to = _parse_date(date_to_str)
    tx_filters = _build_date_filters(Transaction.date, d_from, d_to)

    revenue = (
        db.session.query(func.sum(Transaction.amount))
        .filter(Transaction.transaction_type == 'credit', *tx_filters)
        .scalar() or 0
    )
    total_expenses = (
        db.session.query(func.sum(Transaction.amount))
        .filter(Transaction.transaction_type == 'debit', *tx_filters)
        .scalar() or 0
    )
    client_debited = (
        db.session.query(func.sum(Transaction.amount))
        .filter(Transaction.transaction_type == 'delivery_charge', *tx_filters)
        .scalar() or 0
    )

    profit = revenue - total_expenses
    margin = round(profit / revenue * 100, 1) if revenue else 0.0

    expense_breakdown = _build_expense_breakdown(d_from, d_to, total_expenses)

    def _category_expenses(slug):
        return (
            db.session.query(func.sum(Transaction.amount))
            .join(Settings, Settings.id == Transaction.expense_type_id)
            .join(ExpenseCategory, ExpenseCategory.id == Settings.category_id)
            .filter(Transaction.transaction_type == 'debit', ExpenseCategory.slug == slug, *tx_filters)
            .scalar() or 0
        )

    delivery_expenses = _category_expenses('delivery')
    salary_expenses = _category_expenses('salary')
    flowers_expenses = _category_expenses('flowers')

    delivery_count = (
        db.session.query(func.count(Delivery.id))
        .filter(Delivery.status != 'Скасовано', *_build_date_filters(Delivery.delivery_date, d_from, d_to))
        .scalar() or 0
    )

    revenue_per_delivery = round(revenue / delivery_count) if delivery_count else 0
    flowers_per_delivery = round(flowers_expenses / delivery_count) if delivery_count else 0

    return {
        'revenue': revenue,
        'expenses': total_expenses,
        'client_debited': int(client_debited),
        'profit': profit,
        'margin': margin,
        'expense_breakdown': expense_breakdown,
        'delivery_expenses': delivery_expenses,
        'salary_expenses': salary_expenses,
        'flowers_expenses': flowers_expenses,
        'delivery_count': delivery_count,
        'revenue_per_delivery': revenue_per_delivery,
        'flowers_per_delivery': flowers_per_delivery,
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
        .filter(*_build_date_filters(func.date(FloristSale.created_at), d_from, d_to))
    )

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


def get_cash_flow_data(date_from_str=None, date_to_str=None):
    """Cash flow data. No filter → all-time monthly chart. Filter → daily chart for period."""
    import calendar
    from app.models.transaction import Transaction

    today = date.today()
    UA_MONTHS = [
        'Січень', 'Лютий', 'Березень', 'Квітень', 'Травень', 'Червень',
        'Липень', 'Серпень', 'Вересень', 'Жовтень', 'Листопад', 'Грудень',
    ]

    # ── All-time mode: monthly aggregation ────────────────────────────────────
    if not date_from_str and not date_to_str:
        rows = (
            db.session.query(
                func.extract('year',  Transaction.date).label('y'),
                func.extract('month', Transaction.date).label('m'),
                func.sum(Transaction.amount).label('s'),
            )
            .filter(Transaction.transaction_type == 'credit')
            .group_by('y', 'm')
            .order_by('y', 'm')
            .all()
        )

        monthly = {date(int(r.y), int(r.m), 1): int(r.s) for r in rows}
        labels, values = _fill_monthly_gaps(monthly)

        total = sum(values)

        # Comparison: last complete month vs month before it
        last_month_start = _month_start(today) - timedelta(days=1)
        last_month_start = _month_start(last_month_start)
        prev_month_start = _month_start(last_month_start - timedelta(days=1))
        last_total = monthly.get(last_month_start, 0)
        prev_total = monthly.get(prev_month_start, 0)
        comparison_pct = round(last_total / prev_total * 100, 1) if prev_total > 0 else None

        return {
            'mode': 'monthly',
            'chart': {'labels': labels, 'values': values},
            'total': total,
            'prev_total': prev_total,
            'period_label': 'Весь час',
            'comparison_label': f'{UA_MONTHS[last_month_start.month - 1]} vs {UA_MONTHS[prev_month_start.month - 1]}',
            'comparison_pct': comparison_pct,
        }

    # ── Period mode: daily aggregation ────────────────────────────────────────
    d_from   = _parse_date(date_from_str) or date(today.year, today.month, 1)
    d_to_raw = _parse_date(date_to_str)   or date(today.year, today.month,
                                                   calendar.monthrange(today.year, today.month)[1])

    # Build period label from the original (un-capped) dates
    if (d_from.day == 1
            and d_from.month == d_to_raw.month
            and d_from.year == d_to_raw.year
            and d_to_raw.day == calendar.monthrange(d_from.year, d_from.month)[1]):
        period_label = f'{UA_MONTHS[d_from.month - 1]} {d_from.year}'
    else:
        period_label = f'{d_from.strftime("%d.%m.%Y")} — {d_to_raw.strftime("%d.%m.%Y")}'

    # If the entire period is in the future — return empty
    if d_from > today:
        return {
            'mode': 'daily',
            'chart': {'labels': [], 'values': []},
            'total': 0,
            'prev_total': 0,
            'period_label': period_label,
            'comparison_label': '—',
            'comparison_pct': None,
        }

    d_to = min(d_to_raw, today)

    rows = (
        db.session.query(Transaction.date, func.sum(Transaction.amount))
        .filter(
            Transaction.transaction_type == 'credit',
            Transaction.date >= d_from,
            Transaction.date <= d_to,
        )
        .group_by(Transaction.date)
        .all()
    )

    daily = {row[0]: int(row[1]) for row in rows}
    labels, values = [], []
    cursor = d_from
    while cursor <= d_to:
        labels.append(cursor.strftime('%d.%m'))
        values.append(daily.get(cursor, 0))
        cursor += timedelta(days=1)

    total = sum(values)

    duration = (d_to - d_from).days + 1
    prev_d_from = d_from - timedelta(days=duration)
    prev_d_to   = d_from - timedelta(days=1)
    prev_total = int(
        db.session.query(func.sum(Transaction.amount))
        .filter(
            Transaction.transaction_type == 'credit',
            Transaction.date >= prev_d_from,
            Transaction.date <= prev_d_to,
        )
        .scalar() or 0
    )
    comparison_pct = round(total / prev_total * 100, 1) if prev_total > 0 else None

    return {
        'mode': 'daily',
        'chart': {'labels': labels, 'values': values},
        'total': total,
        'prev_total': prev_total,
        'period_label': period_label,
        'comparison_label': 'Аналогічний попередній період',
        'comparison_pct': comparison_pct,
    }


def get_active_months():
    """Return sorted list of (year, month) that have at least one transaction or delivery."""
    from app.models.transaction import Transaction
    from app.models.delivery import Delivery

    tx_months = db.session.query(
        func.extract('year',  Transaction.date).label('y'),
        func.extract('month', Transaction.date).label('m'),
    ).group_by('y', 'm').all()

    del_months = db.session.query(
        func.extract('year',  Delivery.delivery_date).label('y'),
        func.extract('month', Delivery.delivery_date).label('m'),
    ).group_by('y', 'm').all()

    today = date.today()
    months = {(int(r.y), int(r.m)) for r in tx_months} | {(int(r.y), int(r.m)) for r in del_months}
    # Exclude future months — they have no historical data worth filtering by
    months = {(y, m) for y, m in months if (y, m) <= (today.year, today.month)}
    return sorted(months, reverse=True)  # newest first
