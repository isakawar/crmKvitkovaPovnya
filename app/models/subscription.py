from app.extensions import db
import datetime


class Subscription(db.Model):
    __tablename__ = 'subscription'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)

    # Тип і статус
    type = db.Column(db.String(32), nullable=False)  # Weekly, Monthly, Bi-weekly
    status = db.Column(db.String(32), default='active', nullable=False)  # active, completed, cancelled, draft

    # Розклад
    delivery_day = db.Column(db.String(16), nullable=False)  # ПН/ВТ/СР/ЧТ/ПТ/СБ/НД
    time_from = db.Column(db.String(8))
    time_to = db.Column(db.String(8))

    # Отримувач
    recipient_name = db.Column(db.String(128), nullable=False)
    recipient_phone = db.Column(db.String(32), nullable=False)
    recipient_social = db.Column(db.String(128))

    # Адреса
    city = db.Column(db.String(64), nullable=False)
    street = db.Column(db.String(128), nullable=False)
    building_number = db.Column(db.String(32))
    floor = db.Column(db.String(16))
    entrance = db.Column(db.String(16))
    is_pickup = db.Column(db.Boolean, default=False)
    address_comment = db.Column(db.Text, nullable=True)

    # Метод доставки
    delivery_method = db.Column(db.String(32), default='courier', nullable=False)

    # Розмір
    size = db.Column(db.String(32), nullable=False)
    custom_amount = db.Column(db.Integer)

    # Букет
    bouquet_type = db.Column(db.String(64), nullable=True)
    composition_type = db.Column(db.String(64), nullable=True)

    # Примітки
    for_whom = db.Column(db.String(64), nullable=False)
    comment = db.Column(db.Text)
    preferences = db.Column(db.Text)

    # Весільна підписка
    is_wedding = db.Column(db.Boolean, default=False, nullable=False)

    # Продовження підписки
    is_extended = db.Column(db.Boolean, default=False)
    followup_status = db.Column(db.String(32), nullable=True)
    followup_at = db.Column(db.DateTime, nullable=True)

    # Нагадування про продовження (без замовлень, тільки для дашборду)
    is_renewal_reminder = db.Column(db.Boolean, default=False, nullable=False)

    # Чернетка
    contact_date = db.Column(db.Date, nullable=True)
    draft_comment = db.Column(db.Text, nullable=True)
    draft_bank_link = db.Column(db.String(512), nullable=True)
    draft_wedding_date = db.Column(db.Date, nullable=True)

    # Знижка (%)
    discount = db.Column(db.Integer, nullable=True)

    # Кількість доставок у підписці
    delivery_count = db.Column(db.Integer, nullable=False, default=4)

    # Системні поля
    created_at = db.Column(db.DateTime, default=db.func.now())

    # Зв'язки
    client = db.relationship('Client', backref='subscriptions')
    orders = db.relationship('Order', back_populates='subscription', lazy=True)
