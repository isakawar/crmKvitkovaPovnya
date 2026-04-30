from datetime import datetime
from app.extensions import db


class FloristSale(db.Model):
    __tablename__ = 'florist_sale'

    id            = db.Column(db.Integer, primary_key=True)
    florist_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_by     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount         = db.Column(db.Numeric(10, 2), nullable=False)
    bonus_percent  = db.Column(db.Numeric(5, 2), nullable=False, default=5.0)
    bonus_amount   = db.Column(db.Numeric(10, 2), nullable=False)
    payment_type   = db.Column(db.String(32), nullable=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=True)
    comment        = db.Column(db.Text, nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    florist     = db.relationship('User', foreign_keys=[florist_id], backref='sales')
    creator     = db.relationship('User', foreign_keys=[created_by])
    transaction = db.relationship('Transaction', foreign_keys=[transaction_id])
