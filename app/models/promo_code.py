from datetime import datetime

from app.extensions import db


class PromoCode(db.Model):
    __tablename__ = 'promo_codes'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    discount_percent = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by = db.relationship('User', foreign_keys='[PromoCode.created_by_user_id]')

    def status_display(self):
        return 'Активний' if self.is_active else 'Вимкнений'

    def usage_count(self):
        from app.models.order import Order
        from app.models.subscription import Subscription
        orders_count = Order.query.filter_by(promo_code_id=self.id).count()
        subscriptions_count = Subscription.query.filter_by(promo_code_id=self.id).count()
        return orders_count + subscriptions_count


def generate_promo_code():
    """Generate sequential code: PROMO0001, PROMO0002, ..."""
    prefix = 'PROMO'
    last = (PromoCode.query
            .filter(PromoCode.code.like(f'{prefix}%'))
            .order_by(PromoCode.id.desc())
            .first())
    if last:
        try:
            num = int(last.code[len(prefix):]) + 1
        except (ValueError, IndexError):
            num = 1
    else:
        num = 1
    return f'{prefix}{num:04d}'
