from app.extensions import db
from app.models import Client
import re

def get_all_clients():
    return Client.query.order_by(Client.id.desc()).all()

def get_client_by_id(client_id):
    return Client.query.get_or_404(client_id)

def create_client(instagram, phone=None, telegram=None, credits=0, marketing_source=None, personal_discount=None):
    if not instagram:
        return None, 'Instagram є обовʼязковим!'
    if phone:
        phone = phone.strip()
        if phone:
            phone_pattern = re.compile(r'^\+380[0-9]{9}$')
            if not phone_pattern.match(phone):
                return None, 'Невірний формат номера телефону. Використовуйте формат: +380XXXXXXXXX'
    if phone and Client.query.filter_by(phone=phone).first():
        return None, 'Клієнт з таким номером вже існує!'
    client = Client(
        instagram=instagram,
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
    if phone:
        phone = phone.strip()
        if phone:
            phone_pattern = re.compile(r'^\+380[0-9]{9}$')
            if not phone_pattern.match(phone):
                return None, 'Невірний формат номера телефону. Використовуйте формат: +380XXXXXXXXX'
    if phone:
        existing_client = Client.query.filter_by(phone=phone).first()
        if existing_client and existing_client.id != client_id:
            return None, 'Клієнт з таким номером вже існує!'
    client.instagram = instagram
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