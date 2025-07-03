import pytest
from app import create_app
from models import db, Client, Price, Delivery
from services.order_service import get_or_create_client, check_and_spend_credits, create_order_and_deliveries

@pytest.fixture
def app():
    app = create_app(database_uri='sqlite:///:memory:', seed_data=False)
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
        yield app

@pytest.fixture
def app_context(app):
    with app.app_context():
        yield

def test_order_and_delivery_creation(app_context):
    c = get_or_create_client('+380501231000', 'TestCity', '@tg')
    p = Price(bouquet_size='M', delivery_type='Доставка', price=10)
    db.session.add(p)
    db.session.commit()
    c.credits = 100
    db.session.commit()
    form = {
        'street': 'Test',
        'building_number': '1',
        'entrance': 'A',
        'type': 'Доставка',
        'bouquet_id': str(p.id),
        'delivery_count': '2',
        'preferred_days': ['пн', 'ср'],
        'periodicity': '1/7',
        'time_from': '10:00',
        'time_to': '12:00',
        'comment': 'test',
    }
    class DummyForm:
        def __init__(self, d):
            self.d = d
        def get(self, k, default=None):
            return self.d.get(k, default)
        def getlist(self, k):
            v = self.d.get(k)
            return v if isinstance(v, list) else [v]
        def __getitem__(self, k):
            return self.d[k]
    dummy_form = DummyForm(form)
    ok, _ = check_and_spend_credits(c, p, 2)
    assert ok
    order = create_order_and_deliveries(c, dummy_form)
    deliveries = Delivery.query.filter_by(order_id=order.id).all()
    assert len(deliveries) == 2 