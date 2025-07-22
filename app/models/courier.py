from app.extensions import db

class Courier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    phone = db.Column(db.String(32), nullable=False, unique=True)
    active = db.Column(db.Boolean, default=True)
    deliveries_count = db.Column(db.Integer, default=0)
    delivery_rate = db.Column(db.Integer, default=50)  # Рейт за доставку в гривнях
    deliveries = db.relationship('Delivery', back_populates='courier') 