from app.extensions import db


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False, index=True)

    # Підписка (null для разових замовлень)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=True, index=True)
    sequence_number = db.Column(db.Integer, nullable=True)  # 1-4 для замовлень підписки

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

    # Метод доставки: 'courier' | 'nova_poshta'
    delivery_method = db.Column(db.String(32), default='courier', nullable=False)

    # Розмір
    size = db.Column(db.String(32), nullable=False)
    custom_amount = db.Column(db.Integer)

    # Дата та час
    delivery_date = db.Column(db.Date, nullable=False)
    time_from = db.Column(db.String(8))
    time_to = db.Column(db.String(8))

    # Букет
    bouquet_type = db.Column(db.String(64), nullable=True)
    composition_type = db.Column(db.String(64), nullable=True)

    # Примітки
    for_whom = db.Column(db.String(64), nullable=False)
    comment = db.Column(db.Text)
    preferences = db.Column(db.Text)

    # Знижка (%)
    discount = db.Column(db.Integer, nullable=True)

    # Системні поля
    created_at = db.Column(db.DateTime, default=db.func.now())

    # Зв'язки
    deliveries = db.relationship('Delivery', back_populates='order', lazy=True)
    subscription = db.relationship('Subscription', back_populates='orders')
