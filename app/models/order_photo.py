from datetime import datetime
from app.extensions import db


class OrderPhoto(db.Model):
    __tablename__ = 'order_photos'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    comment = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    order = db.relationship('Order', backref=db.backref('photos', lazy='dynamic'))
    uploader = db.relationship('User', foreign_keys=[uploaded_by])
