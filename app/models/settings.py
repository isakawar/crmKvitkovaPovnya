from app.extensions import db

class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False, index=True)
    value = db.Column(db.String(100), nullable=False, index=True)
    sort_order = db.Column(db.Integer, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id'), nullable=True)

    category = db.relationship('ExpenseCategory', backref='expense_types')

    #: Довідник має бути однозначним: get_order_price шукає розмір через
    #: filter_by(type='size', value=...).first(), і дубль тихо змінював би ціну.
    __table_args__ = (
        db.UniqueConstraint('type', 'value', name='uq_settings_type_value'),
    )

    def __repr__(self):
        return f'<Settings {self.type}: {self.value}>' 