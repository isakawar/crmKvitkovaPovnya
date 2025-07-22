import pytest
from app import create_app
from app.extensions import db
from app.models import Order, Client, Delivery
from datetime import date

@pytest.fixture
def app():
    """Створює тестове додаток"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Створює тестовий клієнт"""
    return app.test_client()

@pytest.fixture
def db_session(app):
    """Надає сесію бази даних"""
    with app.app_context():
        yield db.session

@pytest.fixture
def sample_client(db_session):
    """Створює тестового клієнта"""
    client = Client(instagram='test_user')
    db_session.add(client)
    db_session.commit()
    return client

@pytest.fixture
def sample_order(db_session, sample_client):
    """Створює тестове замовлення"""
    order = Order(
        client_id=sample_client.id,
        recipient_name='Test User',
        recipient_phone='+380123456789',
        city='Київ',
        street='Test Street',
        delivery_type='Weekly',
        size='M',
        first_delivery_date=date.today(),
        delivery_day='ПН',
        for_whom='дівчина собі'
    )
    db_session.add(order)
    db_session.commit()
    return order 