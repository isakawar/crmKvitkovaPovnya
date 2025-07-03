from app.extensions import db

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    street = db.Column(db.String(128), nullable=False)
    building_number = db.Column(db.String(32))
    floor = db.Column(db.String(16))
    entrance = db.Column(db.String(16))
    size = db.Column(db.String(32))
    type = db.Column(db.String(32))  # разова/постійна
    comment = db.Column(db.Text)
    time_window = db.Column(db.String(64))
    recipient_phone = db.Column(db.String(32))
    periodicity = db.Column(db.String(8))
    preferred_days = db.Column(db.String(64))
    time_from = db.Column(db.String(8))
    time_to = db.Column(db.String(8))
    bouquet_id = db.Column(db.Integer, db.ForeignKey('price.id'))
    bouquet = db.relationship('Price')
    delivery_count = db.Column(db.Integer, default=1)
    # --- denormalized fields ---
    bouquet_size = db.Column(db.String(16))
    delivery_type = db.Column(db.String(32))
    price_at_order = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=db.func.now()) 