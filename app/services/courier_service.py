from app.extensions import db
from app.models import Courier

def get_all_couriers():
    return Courier.query.order_by(Courier.id.desc()).all()

def create_courier(name, phone, delivery_rate=50):
    courier = Courier(name=name, phone=phone, delivery_rate=delivery_rate)
    db.session.add(courier)
    db.session.commit()
    return courier 