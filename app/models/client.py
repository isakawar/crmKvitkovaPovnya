from app.extensions import db

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    instagram = db.Column(db.String(128), nullable=False)
    phone = db.Column(db.String(32), nullable=True)
    telegram = db.Column(db.String(128))
    credits = db.Column(db.Integer, default=0)
    orders = db.relationship('Order', backref='client', lazy=True) 
    marketing_source = db.Column(db.String(64), nullable=True)
    personal_discount = db.Column(db.String(16), nullable=True)