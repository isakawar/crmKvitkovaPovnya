from datetime import datetime
from app.extensions import db


class SaleOption(db.Model):
    __tablename__ = 'sale_option'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), nullable=False)
    tiers_json      = db.Column(db.Text, nullable=False)
    is_active       = db.Column(db.Boolean, default=True, nullable=False)
    sort_order      = db.Column(db.Integer, nullable=True)
    icon_filename   = db.Column(db.String(255), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
