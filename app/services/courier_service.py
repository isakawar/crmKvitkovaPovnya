from app.extensions import db
from app.models import Courier

def get_all_couriers():
    return Courier.query.order_by(Courier.id.desc()).all()

def create_courier(name, phone=None, is_taxi=False,
                   communication_channel=None, nickname=None,
                   working_days=None, comment=None, rating=None):
    if not is_taxi and not phone:
        raise ValueError("Phone is required for non-taxi courier")
    courier = Courier(
        name=name,
        phone=phone or None,
        is_taxi=is_taxi,
        communication_channel=communication_channel or None,
        nickname=nickname or None,
        working_days=working_days or None,
        comment=comment or None,
        rating=rating or None,
    )
    db.session.add(courier)
    db.session.commit()
    return courier

def update_courier(courier, name=None, phone=None, is_taxi=None,
                   communication_channel=None, nickname=None,
                   working_days=None, comment=None, rating=None):
    if name is not None:
        courier.name = name
    if phone is not None:
        courier.phone = phone or None
    if is_taxi is not None:
        courier.is_taxi = is_taxi
    courier.communication_channel = communication_channel or None
    courier.nickname = nickname or None
    courier.working_days = working_days or None
    courier.comment = comment or None
    courier.rating = rating if rating and 1 <= rating <= 5 else None
    db.session.commit()
    return courier
