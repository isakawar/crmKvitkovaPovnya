from datetime import date, datetime
from sqlalchemy import func

from app.extensions import db
from app.models import Client, Order, Settings


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


def _compact(raw_value):
    return ' '.join((raw_value or '').strip().split())


def _label_key(raw_value):
    compact = _compact(raw_value)
    lowered = compact.lower()
    if lowered in UNSPECIFIED_TOKENS:
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


def get_reports_data(selected_month_raw=None):
    month_start = _parse_month(selected_month_raw)
    month_start_dt, month_end_dt = _month_bounds(month_start)

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

    delivery_type_rows = (
        db.session.query(Order.delivery_type, func.count(Order.id))
        .group_by(Order.delivery_type)
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
        'marketing_all_chart': _items_to_chart(marketing_all),
        'marketing_month_chart': _items_to_chart(marketing_month),
        'for_whom_all_chart': _items_to_chart(for_whom_all),
        'for_whom_month_chart': _items_to_chart(for_whom_month),
        'delivery_type_chart': _items_to_chart(delivery_type_all),
        'size_chart': _items_to_chart(size_all),
    }
