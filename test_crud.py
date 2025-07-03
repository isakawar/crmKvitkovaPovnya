import os
import tempfile
import pytest
from flask import Flask
from models import db, Client, Order, Price, Delivery
from app import create_app
import datetime

@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    database_uri = f'sqlite:///{db_path}'
    app = create_app(database_uri=database_uri, seed_data=False)
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
        yield app
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def app_context(app):
    with app.app_context():
        yield

def test_client_crud(app_context):
    c = Client(instagram='@test', phone='+380501231000', city='TestCity', telegram='@tg', credits=10)
    db.session.add(c)
    db.session.commit()
    assert Client.query.count() == 1
    c.city = 'NewCity'
    db.session.commit()
    assert Client.query.first().city == 'NewCity'
    db.session.delete(c)
    db.session.commit()
    assert Client.query.count() == 0

def test_price_crud(app_context):
    p = Price(bouquet_size='M', delivery_type='Доставка', price=100)
    db.session.add(p)
    db.session.commit()
    assert Price.query.count() == 1
    p.price = 200
    db.session.commit()
    assert Price.query.first().price == 200
    db.session.delete(p)
    db.session.commit()
    assert Price.query.count() == 0

def test_order_crud(app_context):
    c = Client(instagram='@test', phone='+380501231000', city='TestCity', telegram='@tg', credits=10)
    db.session.add(c)
    db.session.commit()
    p = Price(bouquet_size='M', delivery_type='Доставка', price=100)
    db.session.add(p)
    db.session.commit()
    o = Order(
        client_id=c.id,
        street='Test',
        building_number='1',
        floor='2',
        entrance='A',
        size='M',
        type='Доставка',
        comment='test',
        time_window='10:00-12:00',
        recipient_phone='+380501231001',
        periodicity='1/7',
        preferred_days='пн,ср',
        time_from='10:00',
        time_to='12:00',
        bouquet_id=p.id,
        delivery_count=1
    )
    db.session.add(o)
    db.session.commit()
    assert Order.query.count() == 1
    o.street = 'NewStreet'
    db.session.commit()
    assert Order.query.first().street == 'NewStreet'
    db.session.delete(o)
    db.session.commit()
    assert Order.query.count() == 0

def test_delivery_crud(app_context):
    c = Client(instagram='@test', phone='+380501231000', city='TestCity', telegram='@tg', credits=10)
    db.session.add(c)
    db.session.commit()
    p = Price(bouquet_size='M', delivery_type='Доставка', price=100)
    db.session.add(p)
    db.session.commit()
    o = Order(
        client_id=c.id,
        street='Test',
        building_number='1',
        floor='2',
        entrance='A',
        size='M',
        type='Доставка',
        comment='test',
        time_window='10:00-12:00',
        recipient_phone='+380501231001',
        periodicity='1/7',
        preferred_days='пн,ср',
        time_from='10:00',
        time_to='12:00',
        bouquet_id=p.id,
        delivery_count=1
    )
    db.session.add(o)
    db.session.commit()
    d = Delivery(
        order_id=o.id,
        client_id=c.id,
        bouquet_id=p.id,
        delivery_date=datetime.date.today(),
        status='Очікує',
        comment='test',
    )
    db.session.add(d)
    db.session.commit()
    assert Delivery.query.count() == 1
    d.status = 'done'
    db.session.commit()
    assert Delivery.query.first().status == 'done'
    db.session.delete(d)
    db.session.commit()
    assert Delivery.query.count() == 0

if __name__ == '__main__':
    pytest.main([__file__]) 