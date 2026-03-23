from datetime import datetime, date

from app.extensions import db


class Certificate(db.Model):
    __tablename__ = 'certificates'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)

    # amount | size | subscription
    type = db.Column(db.String(20), nullable=False)

    # for type='amount'
    value_amount = db.Column(db.Numeric(10, 2), nullable=True)

    # for type='size' and type='subscription'
    value_size = db.Column(db.String(10), nullable=True)

    expires_at = db.Column(db.Date, nullable=False)

    # active | used | expired
    status = db.Column(db.String(20), nullable=False, default='active')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used_at = db.Column(db.DateTime, nullable=True)

    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    order = db.relationship('Order', backref=db.backref('certificate', uselist=False))

    comment = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by = db.relationship('User', foreign_keys='[Certificate.created_by_user_id]')

    def is_active(self):
        return self.status == 'active' and self.expires_at >= date.today()

    def value_display(self):
        if self.type == 'amount':
            return f'{self.value_amount} грн'
        elif self.type == 'size':
            return self.value_size
        elif self.type == 'subscription':
            return f'Підписка / {self.value_size}' if self.value_size else 'Підписка'
        return '—'

    def type_display(self):
        labels = {
            'amount': 'На суму',
            'size': 'На розмір',
            'subscription': 'На підписку',
        }
        return labels.get(self.type, self.type)

    def status_display(self):
        if self.status == 'used':
            return 'Використаний'
        if self.status == 'expired' or (self.status == 'active' and self.expires_at < date.today()):
            return 'Прострочений'
        return 'Активний'

    def effective_status(self):
        if self.status == 'used':
            return 'used'
        if self.expires_at < date.today():
            return 'expired'
        return 'active'


def generate_certificate_code(cert_type):
    """Generate sequential code: П0001 for subscription, Р0001 for others."""
    prefix = 'П' if cert_type == 'subscription' else 'Р'
    last = (Certificate.query
            .filter(Certificate.code.like(f'{prefix}%'))
            .order_by(Certificate.id.desc())
            .first())
    if last:
        try:
            num = int(last.code[1:]) + 1
        except (ValueError, IndexError):
            num = 1
    else:
        num = 1
    return f'{prefix}{num:04d}'
