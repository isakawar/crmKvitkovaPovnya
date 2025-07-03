from flask import Flask, redirect, url_for
from config import Config
from models import db, Client, Order
from routes.orders import orders_bp
from routes.clients import clients_bp
from routes.prices import prices_bp
import random


def seed_db(app):
    with app.app_context():
        if Client.query.count() == 0:
            cities = ['Київ', 'Львів', 'Одеса', 'Харків', 'Дніпро']
            clients = [
                Client(instagram='@testuser1', phone='+380501231001', city='Київ', telegram='@tguser1', credits=10),
                Client(instagram='@testuser2', phone='+380501231002', city='Львів', telegram='@tguser2', credits=20),
                Client(instagram='@testuser3', phone='+380501231003', city='Одеса', telegram='@tguser3', credits=30),
                Client(instagram='@testuser4', phone='+380501231004', city='Харків', telegram='@tguser4', credits=40),
                Client(instagram='@testuser5', phone='+380501231005', city='Дніпро', telegram='@tguser5', credits=50),
            ]
            db.session.add_all(clients)
            db.session.commit()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    app.register_blueprint(orders_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(prices_bp)

    @app.route('/')
    def index():
        return redirect(url_for('orders.orders_list'))

    with app.app_context():
        db.create_all()
        seed_db(app)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5055) 