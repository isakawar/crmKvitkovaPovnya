from datetime import datetime
from app.extensions import db


class RevenueAdjustment(db.Model):
    __tablename__ = 'revenue_adjustment'

    id              = db.Column(db.Integer, primary_key=True)
    client_id       = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=True)
    month           = db.Column(db.Date, nullable=False)
    adj_charged     = db.Column(db.Integer, nullable=False, default=0)
    adj_paid        = db.Column(db.Integer, nullable=False, default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_revenue_adj_client_month', 'client_id', 'month'),
    )
