from app.extensions import db
from app.models import Price
from sqlalchemy.exc import IntegrityError

def get_all_prices():
    return Price.query.order_by(Price.bouquet_size, Price.delivery_type).all()

def create_or_update_price(bouquet_size, delivery_type, price):
    price_obj = Price.query.filter_by(bouquet_size=bouquet_size, delivery_type=delivery_type).first()
    if price_obj:
        price_obj.price = price
    else:
        price_obj = Price(bouquet_size=bouquet_size, delivery_type=delivery_type, price=price)
        db.session.add(price_obj)
    db.session.commit()
    return price_obj

def update_price_by_id(price_id, bouquet_size, delivery_type, price):
    price_obj = Price.query.get(price_id)
    if price_obj:
        price_obj.bouquet_size = bouquet_size
        price_obj.delivery_type = delivery_type
        price_obj.price = price
        try:
            db.session.commit()
            return price_obj, None
        except IntegrityError:
            db.session.rollback()
            return None, 'Така комбінація розміру і типу доставки вже існує!'
    return None, 'Не знайдено запис для оновлення.' 