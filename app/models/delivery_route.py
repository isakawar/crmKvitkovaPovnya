from app.extensions import db
import datetime


class DeliveryRoute(db.Model):
    __tablename__ = 'delivery_routes'

    id = db.Column(db.Integer, primary_key=True)
    courier_id = db.Column(db.Integer, db.ForeignKey('courier.id'), nullable=True)
    route_date = db.Column(db.Date, nullable=False)

    # draft → sent → accepted/rejected → completed
    status = db.Column(db.String(32), default='draft', nullable=False)

    delivery_price = db.Column(db.Integer, nullable=True)       # загальна оплата кур'єру за маршрут
    deliveries_count = db.Column(db.Integer, default=0)
    total_distance_km = db.Column(db.Float, nullable=True)
    estimated_duration_min = db.Column(db.Integer, nullable=True)

    telegram_message_id = db.Column(db.BigInteger, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    accepted_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)

    start_time = db.Column(db.Time, nullable=True)

    cached_result_json = db.Column(db.Text, nullable=True)
    cached_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    courier = db.relationship('Courier', backref='routes')
    stops = db.relationship('RouteDelivery', back_populates='route', order_by='RouteDelivery.stop_order', cascade='all, delete-orphan')


class RouteDelivery(db.Model):
    __tablename__ = 'route_deliveries'

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('delivery_routes.id'), nullable=False)
    delivery_id = db.Column(db.Integer, db.ForeignKey('delivery.id'), nullable=False)
    stop_order = db.Column(db.Integer, nullable=False)

    distance_from_previous_km = db.Column(db.Float, nullable=True)
    duration_from_previous_min = db.Column(db.Integer, nullable=True)

    planned_arrival = db.Column(db.DateTime, nullable=True)
    actual_arrival = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    route = db.relationship('DeliveryRoute', back_populates='stops')
    delivery = db.relationship('Delivery', backref='route_stops')
