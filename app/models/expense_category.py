from app.extensions import db


class ExpenseCategory(db.Model):
    __tablename__ = 'expense_category'
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(50),  nullable=False, unique=True)
