from models import db

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    street = db.Column(db.String(128), nullable=False)
    building_number = db.Column(db.String(32))
    floor = db.Column(db.String(16))
    entrance = db.Column(db.String(16))
    size = db.Column(db.String(32))
    type = db.Column(db.String(32))  # разова/постійна
    comment = db.Column(db.Text)
    time_window = db.Column(db.String(64)) 