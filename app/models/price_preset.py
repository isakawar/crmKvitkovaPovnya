from datetime import datetime
from app.extensions import db


class PricePreset(db.Model):
    __tablename__ = 'price_presets'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    prices = db.relationship('Price', backref='preset', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<PricePreset {self.name} active={self.is_active}>'
