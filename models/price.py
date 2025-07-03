from models import db

class Price(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bouquet_size = db.Column(db.String(16), nullable=False)  # M/L/XL/XXL
    delivery_type = db.Column(db.String(32), nullable=False)  # Доставка/Самовивіз
    price = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint('bouquet_size', 'delivery_type', name='uq_bouquet_delivery'),) 