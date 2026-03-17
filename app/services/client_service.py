from app.extensions import db
from app.models import Client
from sqlalchemy import func, or_
import re

def get_all_clients():
    return Client.query.order_by(Client.id.desc()).all()

def get_client_by_id(client_id):
    return Client.query.get_or_404(client_id)

def create_client(instagram, phone=None, telegram=None, credits=0, marketing_source=None, personal_discount=None):
    if not instagram:
        return None, 'Instagram є обовʼязковим!'
    instagram = instagram.strip()
    normalized_instagram = instagram.lstrip('@')
    if phone:
        phone = phone.strip()
        if phone:
            phone_pattern = re.compile(r'^\+380[0-9]{9}$')
            if not phone_pattern.match(phone):
                return None, 'Невірний формат номера телефону. Використовуйте формат: +380XXXXXXXXX'
    if telegram:
        telegram = telegram.strip()
    if normalized_instagram:
        existing_instagram = Client.query.filter(
            or_(
                func.lower(Client.instagram) == normalized_instagram.lower(),
                func.lower(Client.instagram) == f'@{normalized_instagram.lower()}'
            )
        ).first()
        if existing_instagram:
            return None, {
                'type': 'duplicate',
                'field': 'instagram',
                'client_id': existing_instagram.id,
                'error': 'Клієнт з таким Instagram вже існує. Відкрити його картку?'
            }
    if telegram:
        normalized_telegram = telegram.lstrip('@')
        existing_telegram = Client.query.filter(
            or_(
                func.lower(Client.telegram) == normalized_telegram.lower(),
                func.lower(Client.telegram) == f'@{normalized_telegram.lower()}'
            )
        ).first()
        if existing_telegram:
            return None, {
                'type': 'duplicate',
                'field': 'telegram',
                'client_id': existing_telegram.id,
                'error': 'Клієнт з таким Telegram вже існує. Відкрити його картку?'
            }
    if phone:
        existing_phone = Client.query.filter_by(phone=phone).first()
        if existing_phone:
            return None, {
                'type': 'duplicate',
                'field': 'phone',
                'client_id': existing_phone.id,
                'error': 'Клієнт з таким номером вже існує. Відкрити його картку?'
            }
    client = Client(
        instagram=normalized_instagram,
        phone=phone,
        telegram=telegram,
        credits=credits,
        marketing_source=marketing_source,
        personal_discount=personal_discount
    )
    db.session.add(client)
    db.session.commit()
    return client, None

def update_client(client_id, instagram, phone=None, telegram=None, credits=0, marketing_source=None, personal_discount=None):
    client = get_client_by_id(client_id)
    if not instagram:
        return None, 'Instagram є обовʼязковим!'
    instagram = instagram.strip()
    normalized_instagram = instagram.lstrip('@')
    if phone:
        phone = phone.strip()
        if phone:
            phone_pattern = re.compile(r'^\+380[0-9]{9}$')
            if not phone_pattern.match(phone):
                return None, 'Невірний формат номера телефону. Використовуйте формат: +380XXXXXXXXX'
    if telegram:
        telegram = telegram.strip()
    if normalized_instagram:
        existing_instagram = Client.query.filter(
            or_(
                func.lower(Client.instagram) == normalized_instagram.lower(),
                func.lower(Client.instagram) == f'@{normalized_instagram.lower()}'
            )
        ).first()
        if existing_instagram and existing_instagram.id != client_id:
            return None, 'Клієнт з таким Instagram вже існує!'
    if telegram:
        normalized_telegram = telegram.lstrip('@')
        existing_telegram = Client.query.filter(
            or_(
                func.lower(Client.telegram) == normalized_telegram.lower(),
                func.lower(Client.telegram) == f'@{normalized_telegram.lower()}'
            )
        ).first()
        if existing_telegram and existing_telegram.id != client_id:
            return None, 'Клієнт з таким Telegram вже існує!'
    if phone:
        existing_client = Client.query.filter_by(phone=phone).first()
        if existing_client and existing_client.id != client_id:
            return None, 'Клієнт з таким номером вже існує!'
    client.instagram = normalized_instagram
    client.phone = phone
    client.telegram = telegram
    client.credits = credits
    client.marketing_source = marketing_source
    client.personal_discount = personal_discount
    db.session.commit()
    return client, None

def get_clients_json():
    clients = get_all_clients()
    return [
        {'id': c.id, 'phone': c.phone, 'instagram': c.instagram} for c in clients
    ]

# Додаємо функцію get_clients для сумісності
def get_clients(page=1, per_page=20):
    """Функція для пагінації клієнтів (alias для get_all_clients)"""
    return get_all_clients() 
