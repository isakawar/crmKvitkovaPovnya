from app.extensions import db

class Courier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    phone = db.Column(db.String(32), nullable=False, unique=True)
    active = db.Column(db.Boolean, default=True)
    deliveries_count = db.Column(db.Integer, default=0)

    # Telegram integration fields
    telegram_chat_id = db.Column(db.BigInteger, unique=True, nullable=True)
    telegram_username = db.Column(db.String(64), nullable=True)
    telegram_registered = db.Column(db.Boolean, default=False)
    telegram_notifications_enabled = db.Column(db.Boolean, default=True)
    last_telegram_activity = db.Column(db.DateTime, nullable=True)
    
    deliveries = db.relationship('Delivery', back_populates='courier') 