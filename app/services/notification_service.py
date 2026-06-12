"""
Notification Service — єдина точка агрегації всіх нотифікацій для менеджерів.

Формат кожного елемента:
{
    'type':            str,   # 'action_item' | 'draft' | 'renewal'
    'title':           str,   # ім'я клієнта або назва завдання
    'subtitle':        str,   # підзаголовок (дедлайн, дні прострочення)
    'is_overdue':      bool,
    'url':             str,   # посилання при кліку (з highlight-параметром)
    'action_item_id':  int|None,  # якщо completable через API
}

Щоб додати нове джерело — реалізуй функцію _collect_<source>() і додай її в
get_notifications_for_user() / get_notifications_count_for_user().
"""

from datetime import date


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_notifications_for_user(user_id: int) -> list[dict]:
    """Повертає всі нотифікації для конкретного менеджера."""
    items: list[dict] = []
    items.extend(_collect_action_items(user_id))
    items.extend(_collect_draft_subscriptions())
    items.extend(_collect_renewal_subscriptions())
    return items


def get_notifications_count_for_user(user_id: int) -> int:
    """Scalar count для badge у navbar."""
    return len(get_notifications_for_user(user_id))


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def _collect_action_items(user_id: int) -> list[dict]:
    """Адмін-створені завдання призначені цьому менеджеру."""
    from datetime import datetime
    from app.services.action_item_service import get_pending_for_user
    try:
        now = datetime.utcnow()
        result = []
        for r in get_pending_for_user(user_id):
            ai = r.action_item
            is_overdue = bool(ai.due_at and ai.due_at < now)
            result.append({
                'type': 'action_item',
                'title': ai.title,
                'subtitle': ai.due_at.strftime('%d.%m.%Y %H:%M') if ai.due_at else None,
                'is_overdue': is_overdue,
                'url': None,
                'action_item_id': ai.id,
            })
        return result
    except Exception:
        return []


def _collect_draft_subscriptions() -> list[dict]:
    """Чернетки з датою контакту сьогодні або в минулому."""
    from app.services.subscription_service import get_draft_subscriptions
    try:
        today = date.today()
        result = []
        for sub in get_draft_subscriptions(contact_date_to=today):
            client = sub.client
            name = (client.instagram or client.phone or 'Клієнт') if client else 'Клієнт'
            days = (today - sub.contact_date).days if sub.contact_date else 0
            result.append({
                'type': 'draft',
                'title': name.lstrip('@'),
                'subtitle': f'{days} дн. прострочено' if days > 0 else 'Контакт сьогодні',
                'is_overdue': days > 0,
                'url': f'/dashboard?highlight=draft-{sub.id}',
                'action_item_id': None,
            })
        return result
    except Exception:
        return []


def _collect_renewal_subscriptions() -> list[dict]:
    """Підписки без продовження 5+ днів."""
    from app.services.subscription_service import get_subscriptions_needing_renewal
    try:
        today = date.today()
        result = []
        for row in get_subscriptions_needing_renewal(today):
            days = row.get('days_overdue', 0)
            if days < 5:
                continue
            sub = row['subscription']
            client = row['client']
            name = (client.instagram or client.phone or 'Клієнт') if client else 'Клієнт'
            result.append({
                'type': 'renewal',
                'title': name.lstrip('@'),
                'subtitle': f'{days} дн. без замовлення',
                'is_overdue': True,
                'url': f'/dashboard?highlight=renewal-{sub.id}',
                'action_item_id': None,
            })
        return result
    except Exception:
        return []
