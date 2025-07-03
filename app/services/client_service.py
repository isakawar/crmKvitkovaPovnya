from app.extensions import db
from app.models import Client

def get_all_clients():
    return Client.query.order_by(Client.id.desc()).all()

def create_client(phone, instagram, telegram, credits, city):
    if not city:
        return None, 'Місто є обовʼязковим!'
    if Client.query.filter_by(phone=phone).first():
        return None, 'Клієнт з таким номером вже існує!'
    client = Client(phone=phone, instagram=instagram, telegram=telegram, credits=credits, city=city)
    db.session.add(client)
    db.session.commit()
    return client, None

def get_clients_json():
    clients = get_all_clients()
    return [
        {'id': c.id, 'phone': c.phone, 'instagram': c.instagram, 'city': c.city} for c in clients
    ] 