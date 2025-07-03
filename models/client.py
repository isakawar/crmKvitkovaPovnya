from models import db

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    instagram = db.Column(db.String(128), nullable=False)
    phone = db.Column(db.String(32), nullable=False, unique=True)
    city = db.Column(db.String(64), nullable=False)
    telegram = db.Column(db.String(128))
    credits = db.Column(db.Integer, default=0)
    orders = db.relationship('Order', backref='client', lazy=True) 