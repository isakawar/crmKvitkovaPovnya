from app.extensions import db
from app.models import Client
from sqlalchemy import func, or_
import re

PHONE_PATTERN = re.compile(r'^\+380[0-9]{9}$')


def _handle_match(column, raw: str):
    """Case-insensitive match on a @handle-style column, with or without '@'."""
    normalized = raw.strip().lstrip('@').lower()
    return or_(func.lower(column) == normalized, func.lower(column) == f'@{normalized}')


def find_client_for_contact(channel_type: str, username: str | None = None,
                            phone: str | None = None) -> Client | None:
    """Best-effort exact match for an inbox conversation's contact info.

    Only auto-links on an unambiguous match (exactly one candidate) — a
    channel-appropriate identifier only, never free-text name, and never a
    guess between multiple plausible clients. Returns None otherwise; the
    conversation stays unlinked for a manager to link by hand.
    """
    from app.services.csv_import_service import normalize_phone

    norm_phone = normalize_phone(phone) if phone else None
    candidates = []

    if channel_type == 'instagram' and username:
        candidates = Client.query.filter(_handle_match(Client.instagram, username)).all()
    elif channel_type in ('telegram', 'telegram_personal'):
        if username:
            candidates = Client.query.filter(_handle_match(Client.telegram, username)).all()
        if not candidates and norm_phone:
            candidates = Client.query.filter_by(phone=norm_phone, phone_telegram=True).all()
    elif channel_type == 'whatsapp' and norm_phone:
        candidates = Client.query.filter_by(phone=norm_phone, phone_whatsapp=True).all()
    elif channel_type == 'viber' and norm_phone:
        candidates = Client.query.filter_by(phone=norm_phone, phone_viber=True).all()

    return candidates[0] if len(candidates) == 1 else None


def _client_snapshot(client) -> dict:
    return {
        'name': client.name,
        'instagram': client.instagram,
        'telegram': client.telegram,
        'phone': client.phone,
        'phone_viber': client.phone_viber,
        'phone_telegram': client.phone_telegram,
        'phone_whatsapp': client.phone_whatsapp,
        'email': client.email,
        'marketing_source': client.marketing_source,
        'personal_discount': client.personal_discount,
        'credits': str(client.credits) if client.credits is not None else None,
    }


def get_all_clients():
    return Client.query.order_by(Client.id.desc()).all()


def search_clients(q=None, sub_filter=None, page=1, per_page=28):
    from app.models.subscription import Subscription
    query = Client.query

    if q:
        like_q = f'%{q.lstrip("@")}%'
        query = query.filter(
            or_(
                Client.instagram.ilike(like_q),
                Client.telegram.ilike(like_q),
                Client.phone.contains(q),
                Client.name.ilike(like_q),
            )
        )

    if sub_filter == 'active':
        query = query.filter(
            db.session.query(Subscription.id)
            .filter(Subscription.client_id == Client.id)
            .exists()
        )
    elif sub_filter == 'inactive':
        query = query.filter(
            ~db.session.query(Subscription.id)
            .filter(Subscription.client_id == Client.id)
            .exists()
        )

    return query.order_by(Client.id.desc()).paginate(page=page, per_page=per_page, error_out=False)


def get_client_by_id(client_id):
    return Client.query.get_or_404(client_id)


def find_client_by_handle(column, value, exclude_client_id=None):
    """Знайти клієнта за instagram/telegram-хендлом без урахування регістру і '@'.

    Єдина реалізація цього пошуку на весь проєкт. CSV-імпорт раніше мав власну,
    через ``filter_by(instagram=...)`` — тобто точний збіг із урахуванням
    регістру. Через це «Ivanna» та «ivanna» не збігались, і імпорт заводив
    другого клієнта там, де форма створення показала б дублікат. Оскільки на
    клієнті висить баланс, це роздвоювало гроші.

    ``column`` — ``Client.instagram`` або ``Client.telegram``.
    """
    if not value:
        return None
    normalized = value.strip().lstrip('@').lower()
    if not normalized:
        return None
    q = Client.query.filter(
        or_(func.lower(column) == normalized, func.lower(column) == f'@{normalized}')
    )
    if exclude_client_id:
        q = q.filter(Client.id != exclude_client_id)
    return q.first()


def _validate_contact_fields(instagram, telegram, phone, exclude_client_id=None):
    """Validate uniqueness of contact fields. Returns error dict or None."""
    if instagram:
        existing = find_client_by_handle(Client.instagram, instagram, exclude_client_id)
        if existing:
            return {
                'type': 'duplicate',
                'field': 'instagram',
                'client_id': existing.id,
                'error': 'Клієнт з таким Instagram вже існує. Відкрити його картку?'
            }

    if telegram:
        existing = find_client_by_handle(Client.telegram, telegram, exclude_client_id)
        if existing:
            return {
                'type': 'duplicate',
                'field': 'telegram',
                'client_id': existing.id,
                'error': 'Клієнт з таким Telegram вже існує. Відкрити його картку?'
            }

    if phone:
        q = Client.query.filter_by(phone=phone)
        if exclude_client_id:
            q = q.filter(Client.id != exclude_client_id)
        existing = q.first()
        if existing:
            return {
                'type': 'duplicate',
                'field': 'phone',
                'client_id': existing.id,
                'error': 'Клієнт з таким номером вже існує. Відкрити його картку?'
            }

    return None


def create_client(instagram=None, telegram=None, phone=None, name=None,
                  phone_viber=False, phone_telegram=False, phone_whatsapp=False,
                  credits=0, marketing_source=None, personal_discount=None, email=None):
    instagram = instagram.strip().lstrip('@') if instagram and instagram.strip() else None
    telegram = telegram.strip() if telegram and telegram.strip() else None
    phone = phone.strip() if phone and phone.strip() else None
    name = name.strip() if name and name.strip() else None
    email = email.strip().lower() if email and email.strip() else None

    if not any([instagram, telegram, phone]):
        return None, 'Вкажіть хоча б один контакт: Instagram, Telegram або номер телефону'

    if phone:
        if not PHONE_PATTERN.match(phone):
            return None, {'field': 'phone', 'error': 'Невірний формат номера телефону. Використовуйте формат: +380XXXXXXXXX'}

    dup = _validate_contact_fields(instagram, telegram, phone)
    if dup:
        return None, dup

    client = Client(
        name=name,
        instagram=instagram,
        telegram=telegram,
        phone=phone,
        phone_viber=bool(phone_viber),
        phone_telegram=bool(phone_telegram),
        phone_whatsapp=bool(phone_whatsapp),
        credits=credits,
        marketing_source=marketing_source,
        personal_discount=personal_discount,
        email=email,
    )
    db.session.add(client)
    db.session.commit()

    from flask_login import current_user
    from app.services.activity_log_service import log as _log
    _log(
        current_user._get_current_object() if current_user.is_authenticated else None,
        'create', 'client', client.id,
        f'Створено клієнта {client.name or client.instagram or client.phone or f"#{client.id}"}',
        after_data=_client_snapshot(client),
    )
    return client, None


def update_client(client_id, instagram=None, telegram=None, phone=None, name=None,
                  phone_viber=False, phone_telegram=False, phone_whatsapp=False,
                  marketing_source=None, personal_discount=None, email=None):
    client = get_client_by_id(client_id)
    before = _client_snapshot(client)

    instagram = instagram.strip().lstrip('@') if instagram and instagram.strip() else None
    telegram = telegram.strip() if telegram and telegram.strip() else None
    phone = phone.strip() if phone and phone.strip() else None
    name = name.strip() if name and name.strip() else None
    email = email.strip().lower() if email and email.strip() else None

    if not any([instagram, telegram, phone]):
        return None, 'Вкажіть хоча б один контакт: Instagram, Telegram або номер телефону'

    if phone:
        if not PHONE_PATTERN.match(phone):
            return None, {'field': 'phone', 'error': 'Невірний формат номера телефону. Використовуйте формат: +380XXXXXXXXX'}

    dup = _validate_contact_fields(instagram, telegram, phone, exclude_client_id=client_id)
    if dup:
        return None, dup

    client.name = name
    client.instagram = instagram
    client.telegram = telegram
    client.phone = phone
    client.phone_viber = bool(phone_viber)
    client.phone_telegram = bool(phone_telegram)
    client.phone_whatsapp = bool(phone_whatsapp)
    client.marketing_source = marketing_source
    client.personal_discount = personal_discount
    client.email = email
    db.session.commit()

    from flask_login import current_user
    from app.services.activity_log_service import log as _log
    _log(
        current_user._get_current_object() if current_user.is_authenticated else None,
        'edit', 'client', client.id,
        f'Редаговано клієнта {client.name or client.instagram or client.phone or f"#{client.id}"}',
        before_data=before,
        after_data=_client_snapshot(client),
    )
    return client, None


def get_clients_json():
    clients = get_all_clients()
    return [
        {'id': c.id, 'phone': c.phone, 'instagram': c.instagram, 'telegram': c.telegram, 'name': c.name}
        for c in clients
    ]


def get_clients(page=1, per_page=20):
    return get_all_clients()
