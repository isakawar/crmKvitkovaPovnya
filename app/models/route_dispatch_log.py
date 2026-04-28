import datetime
from app.extensions import db


class RouteDispatchLog(db.Model):
    __tablename__ = 'route_dispatch_logs'

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(
        db.Integer,
        db.ForeignKey('delivery_routes.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    courier_id = db.Column(
        db.Integer,
        db.ForeignKey('courier.id', ondelete='SET NULL'),
        nullable=True,
    )
    sent_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
    )

    sent_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending|accepted|rejected
    responded_at = db.Column(db.DateTime, nullable=True)

    message_text = db.Column(db.Text, nullable=True)
    delivery_price = db.Column(db.Integer, nullable=True)
    deliveries_count = db.Column(db.Integer, nullable=True)
    total_distance_km = db.Column(db.Float, nullable=True)

    route = db.relationship('DeliveryRoute', backref=db.backref('dispatch_logs', lazy='dynamic'))
    courier = db.relationship('Courier', backref=db.backref('dispatch_logs', lazy='dynamic'))
    sent_by = db.relationship('User', backref=db.backref('route_dispatches', lazy='dynamic'))
