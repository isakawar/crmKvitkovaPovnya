"""Google-Places address coordinates: form → Subscription/Order/Delivery
propagation and the route-optimizer payload."""
import datetime

from app.models import Client, Order, Delivery
from app.services.order_service import create_order_and_deliveries, update_order
from app.services.subscription_service import create_subscription
from app.services.route_optimizer_service import _delivery_to_order_json
from app.utils.address_utils import coords_from_form


class FakeForm(dict):
    def getlist(self, key):
        val = self.get(key, [])
        return val if isinstance(val, list) else [val]


def _order_form(**overrides):
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = FakeForm({
        'recipient_name': 'Тест',
        'recipient_phone': '+380991234567',
        'first_delivery_date': tomorrow,
        'city': 'Київ',
        'street': 'Чоколівський бульвар, 6',
        'size': 'M',
        'for_whom': 'Дружина',
        'delivery_method': 'courier',
        'additional_phones': [],
        'latitude': '50.42787',
        'longitude': '30.49061',
        'google_place_id': 'ChIJ_test_place',
        'formatted_address': 'Чоколівський бул., 6, Київ, Україна',
    })
    form.update(overrides)
    return form


def _sub_form(**overrides):
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = FakeForm({
        'recipient_name': 'Тест',
        'recipient_phone': '+380991234567',
        'first_delivery_date': tomorrow,
        'delivery_type': 'Weekly',
        'delivery_day': 'ПН',
        'city': 'Київ',
        'street': 'Чоколівський бульвар, 6',
        'size': 'M',
        'for_whom': 'Дружина',
        'delivery_method': 'courier',
        'delivery_count': '4',
        'additional_phones': [],
        'latitude': '50.42787',
        'longitude': '30.49061',
        'google_place_id': 'ChIJ_test_place',
        'formatted_address': 'Чоколівський бул., 6, Київ, Україна',
    })
    form.update(overrides)
    return form


def _client(session, instagram='coord_client'):
    c = Client(instagram=instagram)
    session.add(c)
    session.commit()
    return c


# ── coords_from_form ─────────────────────────────────────────────────────────

def test_coords_from_form_parses_values():
    d = coords_from_form(FakeForm({'latitude': '50.1', 'longitude': '30.2',
                                   'google_place_id': 'x', 'formatted_address': 'A'}))
    assert d == {'latitude': 50.1, 'longitude': 30.2,
                 'google_place_id': 'x', 'formatted_address': 'A'}


def test_coords_from_form_blank_and_zero_and_garbage_become_none():
    for lat in ('', '0', 'abc', None):
        d = coords_from_form(FakeForm({'latitude': lat, 'longitude': lat}))
        assert d['latitude'] is None and d['longitude'] is None


def test_coords_from_form_pickup_blanks_everything():
    d = coords_from_form(FakeForm({'latitude': '50.1', 'longitude': '30.2'}), is_pickup=True)
    assert all(v is None for v in d.values())


# ── one-time order ───────────────────────────────────────────────────────────

def test_order_stores_coords_and_copies_to_delivery(session):
    client = _client(session)
    order = create_order_and_deliveries(client, _order_form())
    assert float(order.latitude) == 50.42787
    assert float(order.longitude) == 30.49061
    assert order.google_place_id == 'ChIJ_test_place'
    assert order.formatted_address.startswith('Чоколівський')

    delivery = Delivery.query.filter_by(order_id=order.id).one()
    assert float(delivery.latitude) == 50.42787
    assert float(delivery.longitude) == 30.49061
    assert delivery.google_place_id == 'ChIJ_test_place'


def test_pickup_order_has_no_coords(session):
    client = _client(session, 'coord_pickup')
    order = create_order_and_deliveries(client, _order_form(is_pickup='on'))
    assert order.latitude is None and order.longitude is None
    delivery = Delivery.query.filter_by(order_id=order.id).one()
    assert delivery.latitude is None


def test_update_order_refreshes_coords_and_syncs_deliveries(session):
    client = _client(session, 'coord_update')
    order = create_order_and_deliveries(client, _order_form())
    update_order(order, _order_form(latitude='49.99999', longitude='31.11111',
                                    google_place_id='ChIJ_new', formatted_address='Нова, 1'))
    assert float(order.latitude) == 49.99999
    delivery = Delivery.query.filter_by(order_id=order.id).first()
    assert float(delivery.latitude) == 49.99999
    assert delivery.google_place_id == 'ChIJ_new'


# ── subscription ─────────────────────────────────────────────────────────────

def test_subscription_propagates_coords_to_orders_and_deliveries(session):
    client = _client(session, 'coord_sub')
    sub = create_subscription(client, _sub_form())
    assert float(sub.latitude) == 50.42787

    orders = Order.query.filter_by(subscription_id=sub.id).all()
    assert len(orders) == 4
    for o in orders:
        assert float(o.latitude) == 50.42787
        assert o.google_place_id == 'ChIJ_test_place'
        for d in o.deliveries:
            assert float(d.latitude) == 50.42787


# ── route optimizer payload ──────────────────────────────────────────────────

def test_delivery_to_order_json_includes_coords_when_present(session):
    client = _client(session, 'coord_opt')
    order = create_order_and_deliveries(client, _order_form())
    delivery = Delivery.query.filter_by(order_id=order.id).one()
    item = _delivery_to_order_json(delivery)
    assert item['lat'] == 50.42787
    assert item['lng'] == 30.49061


def test_delivery_to_order_json_omits_coords_when_absent(session):
    client = _client(session, 'coord_opt_none')
    order = create_order_and_deliveries(
        client, _order_form(latitude='', longitude='', google_place_id='', formatted_address=''))
    delivery = Delivery.query.filter_by(order_id=order.id).one()
    item = _delivery_to_order_json(delivery)
    assert 'lat' not in item and 'lng' not in item


def test_delivery_to_order_json_falls_back_to_order_coords(session):
    client = _client(session, 'coord_opt_fallback')
    order = create_order_and_deliveries(client, _order_form())
    delivery = Delivery.query.filter_by(order_id=order.id).one()
    delivery.latitude = None
    delivery.longitude = None
    session.commit()
    item = _delivery_to_order_json(delivery)
    assert item['lat'] == 50.42787 and item['lng'] == 30.49061
