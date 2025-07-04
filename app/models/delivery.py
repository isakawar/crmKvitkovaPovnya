from app.extensions import db
import datetime

class Delivery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    delivery_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(32), default='Очікує')  # Очікує, Виконано, Скасовано
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Адреса
    street = db.Column(db.String(128))
    building_number = db.Column(db.String(32))
    floor = db.Column(db.String(16))
    entrance = db.Column(db.String(16))
    is_pickup = db.Column(db.Boolean, default=False)
    
    # Час та розмір
    time_from = db.Column(db.String(8))
    time_to = db.Column(db.String(8))
    size = db.Column(db.String(32))
    phone = db.Column(db.String(32))
    
    # Кур'єр
    courier_id = db.Column(db.Integer, db.ForeignKey('courier.id'))
    delivered_at = db.Column(db.DateTime)
    status_changed_at = db.Column(db.DateTime)
    
    # Зв'язки
    client = db.relationship('Client')
    courier = db.relationship('Courier', back_populates='deliveries')
    
    # --- denormalized fields ---
    bouquet_size = db.Column(db.String(16))
    delivery_type = db.Column(db.String(32))
    price_at_delivery = db.Column(db.Integer) 