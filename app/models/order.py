from app.extensions import db

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    
    # Отримувач
    recipient_name = db.Column(db.String(128), nullable=False)
    recipient_phone = db.Column(db.String(32), nullable=False)
    recipient_social = db.Column(db.String(128))  # Instagram/Telegram
    
    # Адреса
    city = db.Column(db.String(64), nullable=False)
    street = db.Column(db.String(128), nullable=False)
    building_number = db.Column(db.String(32))
    floor = db.Column(db.String(16))
    entrance = db.Column(db.String(16))
    is_pickup = db.Column(db.Boolean, default=False)  # Самовивіз
    
    # Доставка
    delivery_type = db.Column(db.String(32), nullable=False)  # Weekly, Monthly, Bi-weekly, One-time
    
    # Розмір
    size = db.Column(db.String(32), nullable=False)  # M/L/XL/XXL/Custom
    custom_amount = db.Column(db.Integer)  # Сума для власного розміру
    
    # Дати та час
    first_delivery_date = db.Column(db.Date, nullable=False)
    delivery_day = db.Column(db.String(16), nullable=False)  # ПН/ВТ/СР/ЧТ/ПТ/СБ/НД
    time_from = db.Column(db.String(8))
    time_to = db.Column(db.String(8))
    
    # Додаткова інформація
    comment = db.Column(db.Text)
    preferences = db.Column(db.Text)  # Побажання
    for_whom = db.Column(db.String(64), nullable=False)  # Для кого
    
    # Системні поля
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    # Зв'язки
    deliveries = db.relationship('Delivery', backref='order', lazy=True)
    
    # --- denormalized fields ---
    bouquet_size = db.Column(db.String(16))
    price_at_order = db.Column(db.Integer)
    periodicity = db.Column(db.String(8))
    preferred_days = db.Column(db.String(64)) 