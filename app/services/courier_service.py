from app.extensions import db
from app.models import Courier

def get_all_couriers():
    return Courier.query.order_by(Courier.id.desc()).all()

def create_courier(name, phone=None, is_taxi=False):
    if not is_taxi and not phone:
        raise ValueError("Phone is required for non-taxi courier")
    courier = Courier(name=name, phone=phone or None, is_taxi=is_taxi)
    db.session.add(courier)
    db.session.commit()
    return courier
