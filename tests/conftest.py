"""
Shared pytest fixtures for the CRM Kvitkova Povnya test suite.
Uses SQLite in-memory database so no Postgres is required.

Strategy: function-scoped app + db — tables are created and dropped for each
test, guaranteeing full isolation without any transaction-rollback tricks.
This is slightly slower but works cleanly with SQLAlchemy 2.x.
"""
import pytest
from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models import Client, Courier, Order, Delivery
from app.models.subscription import Subscription
import datetime


@pytest.fixture
def app():
    """Flask app with a fresh in-memory SQLite DB per test."""
    flask_app = create_app(TestingConfig)
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['LOGIN_DISABLED'] = True
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def session(app):
    """Return the active db.session (already inside the app context)."""
    return _db.session


@pytest.fixture
def client_fixture(session):
    c = Client(instagram='test_user')
    session.add(c)
    session.commit()
    return c


@pytest.fixture
def courier_fixture(session):
    c = Courier(name='Іван', phone='+380991234567', deliveries_count=0)
    session.add(c)
    session.commit()
    return c


@pytest.fixture
def subscription_fixture(client_fixture, session):
    sub = Subscription(
        client_id=client_fixture.id,
        type='Weekly',
        status='active',
        delivery_day='ПН',
        recipient_name='Отримувач',
        recipient_phone='+380991234567',
        city='Київ',
        street='Хрещатик 1',
        size='M',
        for_whom='Дружина',
    )
    session.add(sub)
    session.commit()
    return sub


@pytest.fixture
def order_with_delivery(client_fixture, subscription_fixture, session):
    today = datetime.date.today()
    order = Order(
        client_id=client_fixture.id,
        subscription_id=subscription_fixture.id,
        sequence_number=1,
        recipient_name='Отримувач',
        recipient_phone='+380991234567',
        city='Київ',
        street='Хрещатик 1',
        is_pickup=False,
        delivery_method='courier',
        size='M',
        delivery_date=today,
        for_whom='Дружина',
    )
    session.add(order)
    session.flush()

    delivery = Delivery(
        order_id=order.id,
        client_id=client_fixture.id,
        delivery_date=today,
        status='Очікує',
        size='M',
        phone='+380991234567',
        delivery_method='courier',
    )
    session.add(delivery)
    session.commit()
    return order, delivery
