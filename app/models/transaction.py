from datetime import datetime
from app.extensions import db


class Transaction(db.Model):
    __tablename__ = 'transaction'

    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.String(16), nullable=False, default='credit')  # 'credit' | 'debit'
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    amount = db.Column(db.Integer, nullable=False)
    payment_type = db.Column(db.String(32), nullable=True)   # 'monobank' | 'cash' (credits only)
    expense_type = db.Column(db.String(64), nullable=True)   # for debits (future parameters)
    comment = db.Column(db.Text, nullable=True)
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship('Client', backref='transactions', foreign_keys=[client_id])
