from app.extensions import db


class WixProductMapping(db.Model):
    __tablename__ = 'wix_product_mapping'

    id = db.Column(db.Integer, primary_key=True)
    catalog_item_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    wix_item_name = db.Column(db.String(255), nullable=True)
    order_scenario = db.Column(db.String(16), nullable=False)  # order | subscription
    delivery_type = db.Column(db.String(32), nullable=True)  # Weekly | Monthly | Bi-weekly
    size = db.Column(db.String(32), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
