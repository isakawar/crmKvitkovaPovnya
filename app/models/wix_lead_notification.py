from datetime import datetime

from app.extensions import db


class WixLeadNotification(db.Model):
    __tablename__ = 'wix_lead_notification'

    id = db.Column(db.Integer, primary_key=True)
    wix_lead_id = db.Column(db.Integer, db.ForeignKey('wix_lead.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    telegram_chat_id = db.Column(db.BigInteger, nullable=False)
    telegram_message_id = db.Column(db.Integer, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    lead = db.relationship('WixLead', foreign_keys=[wix_lead_id])
    user = db.relationship('User', foreign_keys=[user_id])
