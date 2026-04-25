from app.extensions import db
from app.models import Client
from sqlalchemy import func, or_
import re

PHONE_PATTERN = re.compile(r'^\+380[0-9]{9}$')


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


def _validate_contact_fields(instagram, telegram, phone, exclude_client_id=None):
    """Validate uniqueness of contact fields. Returns error dict or None."""
    if instagram:
        normalized = instagram.lstrip('@')
        q = Client.query.filter(
            or_(
                func.lower(Client.instagram) == normalized.lower(),
                func.lower(Client.instagram) == f'@{normalized.lower()}'
            )
        )
        if exclude_client_id:
            q = q.filter(Client.id != exclude_client_id)
        existing = q.first()
        if existing:
            return {
                'type': 'duplicate',
                'field': 'instagram',
                'client_id': existing.id,
                'error': 'Клієнт з таким Instagram вже існує. Відкрити його картку?'
            }

    if telegram:
        normalized = telegram.lstrip('@')
        q = Client.query.filter(
            or_(
                func.lower(Client.telegram) == normalized.lower(),
                func.lower(Client.telegram) == f'@{normalized.lower()}'
            )
        )
        if exclude_client_id:
            q = q.filter(Client.id != exclude_client_id)
        existing = q.first()
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
    return client, None


def update_client(client_id, instagram=None, telegram=None, phone=None, name=None,
                  phone_viber=False, phone_telegram=False, phone_whatsapp=False,
                  credits=0, marketing_source=None, personal_discount=None, email=None):
    client = get_client_by_id(client_id)

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
    client.credits = credits
    client.marketing_source = marketing_source
    client.personal_discount = personal_discount
    client.email = email
    db.session.commit()
    return client, None


def get_clients_json():
    clients = get_all_clients()
    return [
        {'id': c.id, 'phone': c.phone, 'instagram': c.instagram, 'telegram': c.telegram, 'name': c.name}
        for c in clients
    ]


def get_clients(page=1, per_page=20):
    return get_all_clients()
