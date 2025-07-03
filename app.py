from flask import Flask, redirect, url_for
from config import Config
from models import db, Client, Order, Price, Delivery
from routes.orders import orders_bp
from routes.clients import clients_bp
from routes.prices import prices_bp
from routes.deliveries import deliveries_bp
import random
import datetime


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

def seed_test_data(app):
    with app.app_context():
        if not Client.query.first():
            c1 = Client(instagram='@testuser1', phone='+380501231001', city='Київ', telegram='@tguser1', credits=100)
            c2 = Client(instagram='@testuser2', phone='+380501231002', city='Бровари', telegram='@tguser2', credits=50)
            db.session.add_all([c1, c2])
            db.session.commit()
        if not Price.query.first():
            p1 = Price(bouquet_size='M', delivery_type='Доставка', price=10)
            p2 = Price(bouquet_size='L', delivery_type='Доставка', price=20)
            p3 = Price(bouquet_size='M', delivery_type='Самовивіз', price=8)
            db.session.add_all([p1, p2, p3])
            db.session.commit()
        if not Order.query.first():
            client = Client.query.first()
            bouquet = Price.query.filter_by(bouquet_size='M', delivery_type='Доставка').first()
            order = Order(client_id=client.id, street='Тестова 1', building_number='10', entrance='1', type='Доставка', comment='Тестове замовлення', bouquet_id=bouquet.id, delivery_count=2, recipient_phone='+380501231003', periodicity='1/7', preferred_days='пн,ср', time_from='10:00', time_to='12:00')
            db.session.add(order)
            db.session.commit()
            # Доставки на найближчий понеділок і середу
            today = datetime.date.today()
            days_map = {'пн':0, 'вт':1, 'ср':2, 'чт':3, 'пт':4, 'сб':5, 'нд':6}
            for d in ['пн','ср']:
                delta = (days_map[d] - today.weekday() + 7) % 7
                delivery_date = today + datetime.timedelta(days=delta)
                delivery = Delivery(order_id=order.id, client_id=client.id, bouquet_id=bouquet.id, delivery_date=delivery_date)
                db.session.add(delivery)
            db.session.commit()

def create_app(database_uri=None, seed_data=True):
    app = Flask(__name__)
    app.config.from_object(Config)
    if database_uri:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    db.init_app(app)
    app.register_blueprint(orders_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(prices_bp)
    app.register_blueprint(deliveries_bp)

    @app.route('/')
    def index():
        return redirect(url_for('orders.orders_list'))

    with app.app_context():
        db.create_all()
        if seed_data:
            seed_db(app)
            seed_test_data(app)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5055) 