from app.extensions import db
import datetime

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=True)
    instagram = db.Column(db.String(128), nullable=True, index=True)
    telegram = db.Column(db.String(128), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    phone_viber = db.Column(db.Boolean, nullable=False, default=False)
    phone_telegram = db.Column(db.Boolean, nullable=False, default=False)
    phone_whatsapp = db.Column(db.Boolean, nullable=False, default=False)
    email = db.Column(db.String(256), nullable=True)
    credits = db.Column(db.Integer, default=0)
    marketing_source = db.Column(db.String(64), nullable=True)
    personal_discount = db.Column(db.String(16), nullable=True)
    created_at = db.Column(db.Date, nullable=True, default=datetime.date.today)
    orders = db.relationship('Order', backref='client', lazy=True)

    @property
    def display_name(self):
        """Primary display identifier: instagram → telegram → phone → name → id"""
        if self.instagram:
            return f'@{self.instagram.lstrip("@")}'
        if self.telegram:
            return f'@{self.telegram.lstrip("@")}'
        if self.phone:
            return self.phone
        if self.name:
            return self.name
        return f'#{self.id}'

    @property
    def avatar_letter(self):
        if self.instagram:
            return self.instagram.lstrip('@')[0].upper()
        if self.telegram:
            return self.telegram.lstrip('@')[0].upper()
        if self.name:
            return self.name[0].upper()
        if self.phone:
            return self.phone[-1]
        return '?'