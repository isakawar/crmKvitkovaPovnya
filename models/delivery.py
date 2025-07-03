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
    # relationships
    order = db.relationship('Order')
    client = db.relationship('Client')
    bouquet = db.relationship('Price') 