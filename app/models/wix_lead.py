from datetime import datetime

from app.extensions import db


class WixLead(db.Model):
    __tablename__ = 'wix_lead'

    id = db.Column(db.Integer, primary_key=True)
    wix_order_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    wix_order_number = db.Column(db.String(32), nullable=True)
    raw_payload = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(16), nullable=False, default='new')  # new | processed | ignored

    received_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    contact_name = db.Column(db.String(255), nullable=True)
    contact_phone = db.Column(db.String(32), nullable=True)
    contact_email = db.Column(db.String(256), nullable=True)

    city = db.Column(db.String(128), nullable=True)
    street = db.Column(db.String(500), nullable=True)
    postal_code = db.Column(db.String(16), nullable=True)
    address_comment = db.Column(db.Text, nullable=True)

    item_name = db.Column(db.String(255), nullable=True)
    catalog_item_id = db.Column(db.String(64), nullable=True, index=True)
    quantity = db.Column(db.Integer, nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=True)
    currency = db.Column(db.String(8), nullable=True)
    payment_status = db.Column(db.String(32), nullable=True)
    line_items_count = db.Column(db.Integer, nullable=True)

    matched_client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    mapping_matched = db.Column(db.Boolean, nullable=False, default=False)

    processed_order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    processed_subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    processed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    matched_client = db.relationship('Client', foreign_keys=[matched_client_id])
    processed_order = db.relationship('Order', foreign_keys=[processed_order_id])
    processed_subscription = db.relationship('Subscription', foreign_keys=[processed_subscription_id])
    processed_by = db.relationship('User', foreign_keys=[processed_by_user_id])
