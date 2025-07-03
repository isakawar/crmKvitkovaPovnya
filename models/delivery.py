from models import db
import datetime

class Delivery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    bouquet_id = db.Column(db.Integer, db.ForeignKey('price.id'))
    delivery_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(32), default='Очікує')  # Очікує, Виконано, Скасовано
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    street = db.Column(db.String(128))
    building_number = db.Column(db.String(32))
    time_window = db.Column(db.String(64))
    size = db.Column(db.String(32))
    phone = db.Column(db.String(32))
    time_from = db.Column(db.String(8))
    time_to = db.Column(db.String(8))
    # relationships
    order = db.relationship('Order')
    client = db.relationship('Client')
    bouquet = db.relationship('Price') 