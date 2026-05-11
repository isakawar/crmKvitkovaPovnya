from datetime import datetime
from app.extensions import db


class Transaction(db.Model):
    __tablename__ = 'transaction'

    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.String(16), nullable=False, default='credit')  # 'credit' | 'debit' | 'delivery_charge'
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_type = db.Column(db.String(32), nullable=True)   # 'monobank' | 'cash' (credits only)
    expense_type = db.Column(db.String(64), nullable=True)   # for debits (future parameters)
    comment = db.Column(db.Text, nullable=True)
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    expense_type_id = db.Column(db.Integer, db.ForeignKey('settings.id'), nullable=True)
    payment_account_id = db.Column(db.Integer, db.ForeignKey('settings.id'), nullable=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey('delivery.id', ondelete='SET NULL'), nullable=True)

    client = db.relationship('Client', backref='transactions', foreign_keys=[client_id])
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    expense_type_setting = db.relationship('Settings', foreign_keys=[expense_type_id])
    payment_account_setting = db.relationship('Settings', foreign_keys=[payment_account_id])
    delivery = db.relationship('Delivery', foreign_keys=[delivery_id])
