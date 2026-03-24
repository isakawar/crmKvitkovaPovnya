from app.extensions import db


class RecipientPhone(db.Model):
    __tablename__ = 'recipient_phone'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    phone = db.Column(db.String(32), nullable=False)
    position = db.Column(db.Integer, default=1)

    order = db.relationship('Order', backref='additional_phones')
