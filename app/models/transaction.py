from datetime import datetime
from app.extensions import db


class Transaction(db.Model):
    __tablename__ = 'transaction'

    id = db.Column(db.Integer, primary_key=True)
    #: Канонічний перелік — app.constants.TRANSACTION_TYPES
    #: ('credit' | 'debit' | 'delivery_charge' | 'transfer' | 'adjustment').
    #: Типи, що рухають client.credits, і знак впливу — BALANCE_SIGN_BY_TXN_TYPE.
    transaction_type = db.Column(db.String(16), nullable=False, default='credit')
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_type = db.Column(db.String(32), nullable=True)   # 'monobank' | 'cash' (credits only)
    #: LEGACY. Текстова копія назви типу витрати, залишена з часів, коли FK ще не
    #: було. Джерело правди — expense_type_id; уся звітність рахує витрати ТІЛЬКИ
    #: по ньому. Ця колонка лишається як денормалізований підпис для списку
    #: транзакцій і CSV-експорту (там показується назва на момент операції, яка
    #: не змінюється, якщо тип потім перейменують). Нової логіки на неї вішати
    #: не можна — тільки читання для відображення.
    expense_type = db.Column(db.String(64), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    expense_type_id = db.Column(db.Integer, db.ForeignKey('settings.id'), nullable=True)
    payment_account_id = db.Column(db.Integer, db.ForeignKey('settings.id'), nullable=True, index=True)
    target_payment_account_id = db.Column(db.Integer, db.ForeignKey('settings.id'), nullable=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey('delivery.id', ondelete='SET NULL'), nullable=True, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id', ondelete='SET NULL'), nullable=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id', ondelete='SET NULL'), nullable=True, index=True)

    #: Домінантний патерн звітів — фільтр за типом + діапазоном дат, тож індекс
    #: композитний. Оголошений тут, а не через index=True на колонці, щоб модель
    #: і міграція описували рівно один і той самий індекс.
    __table_args__ = (
        db.Index('ix_transaction_type_date', 'transaction_type', 'date'),
    )

    client = db.relationship('Client', backref='transactions', foreign_keys=[client_id])
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    expense_type_setting = db.relationship('Settings', foreign_keys=[expense_type_id])
    payment_account_setting = db.relationship('Settings', foreign_keys=[payment_account_id])
    target_payment_account_setting = db.relationship('Settings', foreign_keys=[target_payment_account_id])
    delivery = db.relationship('Delivery', foreign_keys=[delivery_id])
    order = db.relationship('Order', foreign_keys=[order_id])
    subscription = db.relationship('Subscription', foreign_keys=[subscription_id])
