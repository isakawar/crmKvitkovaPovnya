import copy

from app.models.wix_lead import WixLead
from app.models.wix_product_mapping import WixProductMapping


SAMPLE_WIX_PAYLOAD = {
    "data": {
        "id": "3521b3e3-cf2d-4093-9b77-b562f6f03165",
        "orderNumber": "10255",
        "paymentStatus": "NOT_PAID",
        "currency": "UAH",
        "buyerEmail": "isakawar1@gmail.com",
        "context": {
            "metaSiteId": "2c31eac1-a4f1-4fd2-886d-361377a42a1f",
            "activationId": "696c1548-f824-409a-aba1-6e621f9e69d7",
        },
        "contact": {
            "name": {"first": "Влад", "last": "Білобров"},
            "email": "isakawar1@gmail.com",
            "phones": [
                {"e164Phone": "+380666746225", "primary": True},
                {"e164Phone": "+380661496436", "primary": False},
            ],
        },
        "lineItems": [
            {
                "quantity": 1,
                "catalogItemId": "977be4c1-a0f7-756d-7540-cf98f9208833",
                "itemName": "Підписка на квіти М (4 доставки)",
                "totalPrice": {"value": "6800.00", "currency": "UAH"},
            }
        ],
        "shippingInfo": {
            "logistics": {
                "shippingDestination": {
                    "address": {
                        "city": "Київ",
                        "addressLine": "вул. Зарічна, 1Г",
                        "postalCode": "02000",
                    },
                    "contactDetails": {
                        "firstName": "Владисла",
                        "lastName": "Білобров",
                        "phone": "+380661496436",
                    },
                }
            }
        },
        "priceSummary": {"total": {"value": "6800.00", "currency": "UAH"}},
    }
}


def test_wix_lead_and_mapping_models_roundtrip(session):
    mapping = WixProductMapping(
        catalog_item_id='977be4c1-a0f7-756d-7540-cf98f9208833',
        wix_item_name='Підписка на квіти М (4 доставки)',
        order_scenario='subscription',
        delivery_type='Monthly',
        size='M',
        for_whom='Дружина',
    )
    session.add(mapping)
    session.commit()

    lead = WixLead(
        wix_order_id='3521b3e3-cf2d-4093-9b77-b562f6f03165',
        wix_order_number='10255',
        raw_payload={'id': '3521b3e3-cf2d-4093-9b77-b562f6f03165'},
        status='new',
    )
    session.add(lead)
    session.commit()

    fetched = WixLead.query.filter_by(wix_order_id='3521b3e3-cf2d-4093-9b77-b562f6f03165').first()
    assert fetched is not None
    assert fetched.status == 'new'
    assert fetched.raw_payload == {'id': '3521b3e3-cf2d-4093-9b77-b562f6f03165'}

    fetched_mapping = WixProductMapping.query.filter_by(
        catalog_item_id='977be4c1-a0f7-756d-7540-cf98f9208833'
    ).first()
    assert fetched_mapping.size == 'M'
    assert fetched_mapping.is_active is True


def test_parse_wix_payload_extracts_expected_fields():
    from app.services.wix_integration_service import parse_wix_payload

    parsed = parse_wix_payload(copy.deepcopy(SAMPLE_WIX_PAYLOAD))

    assert parsed['wix_order_id'] == '3521b3e3-cf2d-4093-9b77-b562f6f03165'
    assert parsed['wix_order_number'] == '10255'
    assert parsed['meta_site_id'] == '2c31eac1-a4f1-4fd2-886d-361377a42a1f'
    assert parsed['contact_name'] == 'Влад Білобров'
    assert parsed['contact_phone'] == '+380666746225'
    assert parsed['contact_email'] == 'isakawar1@gmail.com'
    assert parsed['city'] == 'Київ'
    assert parsed['street'] == 'вул. Зарічна, 1Г'
    assert parsed['postal_code'] == '02000'
    assert parsed['item_name'] == 'Підписка на квіти М (4 доставки)'
    assert parsed['catalog_item_id'] == '977be4c1-a0f7-756d-7540-cf98f9208833'
    assert parsed['quantity'] == 1
    assert parsed['amount'] == '6800.00'
    assert parsed['currency'] == 'UAH'
    assert parsed['payment_status'] == 'NOT_PAID'
    assert parsed['line_items_count'] == 1


def test_parse_wix_payload_falls_back_to_shipping_contact_phone():
    from app.services.wix_integration_service import parse_wix_payload

    payload = copy.deepcopy(SAMPLE_WIX_PAYLOAD)
    payload['data']['contact']['phones'] = []
    payload['data']['contact']['name'] = {}

    parsed = parse_wix_payload(payload)

    assert parsed['contact_phone'] == '+380661496436'
    assert parsed['contact_name'] == 'Владисла Білобров'


def test_parse_wix_payload_handles_missing_data_wrapper():
    from app.services.wix_integration_service import parse_wix_payload

    parsed = parse_wix_payload(copy.deepcopy(SAMPLE_WIX_PAYLOAD)['data'])
    assert parsed['wix_order_id'] == '3521b3e3-cf2d-4093-9b77-b562f6f03165'


def test_find_matching_client_by_phone(session):
    from app.models import Client
    from app.services.wix_integration_service import find_matching_client

    client = Client(instagram='vlad_flowers', phone='+380666746225')
    session.add(client)
    session.commit()

    found = find_matching_client({'contact_phone': '+380666746225', 'contact_email': None})
    assert found is not None
    assert found.id == client.id


def test_find_matching_client_by_email_when_phone_not_found(session):
    from app.models import Client
    from app.services.wix_integration_service import find_matching_client

    client = Client(instagram='other_client', email='isakawar1@gmail.com')
    session.add(client)
    session.commit()

    found = find_matching_client({'contact_phone': '+380000000000', 'contact_email': 'isakawar1@gmail.com'})
    assert found is not None
    assert found.id == client.id


def test_find_matching_client_returns_none_when_no_match(session):
    from app.services.wix_integration_service import find_matching_client

    found = find_matching_client({'contact_phone': '+380000000000', 'contact_email': 'nobody@example.com'})
    assert found is None


def test_find_product_mapping_active_only(session):
    from app.services.wix_integration_service import find_product_mapping

    active = WixProductMapping(
        catalog_item_id='cat-1', order_scenario='order', size='M', is_active=True
    )
    inactive = WixProductMapping(
        catalog_item_id='cat-2', order_scenario='order', size='L', is_active=False
    )
    session.add_all([active, inactive])
    session.commit()

    assert find_product_mapping('cat-1').id == active.id
    assert find_product_mapping('cat-2') is None
    assert find_product_mapping(None) is None
    assert find_product_mapping('unknown') is None


def test_create_or_update_lead_creates_new_lead(session):
    from app.services.wix_integration_service import parse_wix_payload, create_or_update_lead

    payload = copy.deepcopy(SAMPLE_WIX_PAYLOAD)
    parsed = parse_wix_payload(payload)

    lead = create_or_update_lead(payload, parsed)

    assert lead.id is not None
    assert lead.wix_order_id == '3521b3e3-cf2d-4093-9b77-b562f6f03165'
    assert lead.status == 'new'
    assert lead.contact_phone == '+380666746225'
    assert lead.mapping_matched is False
    assert lead.matched_client_id is None
    assert WixLead.query.count() == 1


def test_create_or_update_lead_is_idempotent_on_wix_order_id(session):
    from app.services.wix_integration_service import parse_wix_payload, create_or_update_lead

    payload = copy.deepcopy(SAMPLE_WIX_PAYLOAD)
    parsed = parse_wix_payload(payload)

    first = create_or_update_lead(payload, parsed)
    second = create_or_update_lead(payload, parsed)

    assert first.id == second.id
    assert WixLead.query.count() == 1


def test_create_or_update_lead_does_not_overwrite_processed_lead(session):
    from app.services.wix_integration_service import parse_wix_payload, create_or_update_lead

    payload = copy.deepcopy(SAMPLE_WIX_PAYLOAD)
    parsed = parse_wix_payload(payload)

    lead = create_or_update_lead(payload, parsed)
    lead.status = 'processed'
    session.commit()

    payload['data']['contact']['name'] = {'first': 'Changed', 'last': 'Name'}
    parsed2 = parse_wix_payload(payload)
    result = create_or_update_lead(payload, parsed2)

    assert result.id == lead.id
    assert result.status == 'processed'
    assert result.contact_name != 'Changed Name'


def test_create_or_update_lead_sets_matched_client_and_mapping(session):
    from app.services.wix_integration_service import parse_wix_payload, create_or_update_lead
    from app.models import Client

    client = Client(instagram='vlad', phone='+380666746225')
    mapping = WixProductMapping(
        catalog_item_id='977be4c1-a0f7-756d-7540-cf98f9208833',
        order_scenario='subscription',
        delivery_type='Monthly',
        size='M',
    )
    session.add_all([client, mapping])
    session.commit()

    payload = copy.deepcopy(SAMPLE_WIX_PAYLOAD)
    parsed = parse_wix_payload(payload)
    lead = create_or_update_lead(payload, parsed)

    assert lead.matched_client_id == client.id
    assert lead.mapping_matched is True


def test_create_or_update_lead_raises_without_order_id(session):
    from app.services.wix_integration_service import create_or_update_lead
    import pytest

    with pytest.raises(ValueError):
        create_or_update_lead({}, {'wix_order_id': None})


def test_mark_lead_processed_with_order(session, client_fixture):
    from app.services.wix_integration_service import mark_lead_processed
    from app.models.user import User
    from app.models.order import Order
    import datetime as _dt

    lead = WixLead(
        wix_order_id='order-1', raw_payload={}, status='new',
    )
    order = Order(
        client_id=client_fixture.id, recipient_name='Х', recipient_phone='+380000000000',
        city='Київ', street='вул.', size='M', delivery_date=_dt.date.today(), for_whom='Дружина',
    )
    user = User(username='mgr', email='mgr@example.com', user_type='manager')
    user.set_password('x')
    session.add_all([lead, order, user])
    session.commit()

    mark_lead_processed(lead, order, user)

    assert lead.status == 'processed'
    assert lead.processed_order_id == order.id
    assert lead.processed_subscription_id is None
    assert lead.processed_by_user_id == user.id
    assert lead.processed_at is not None


def test_mark_lead_processed_with_subscription(session, subscription_fixture):
    from app.services.wix_integration_service import mark_lead_processed
    from app.models.user import User

    lead = WixLead(wix_order_id='order-2', raw_payload={}, status='new')
    user = User(username='mgr2', email='mgr2@example.com', user_type='admin')
    user.set_password('x')
    session.add_all([lead, user])
    session.commit()

    mark_lead_processed(lead, subscription_fixture, user)

    assert lead.status == 'processed'
    assert lead.processed_subscription_id == subscription_fixture.id
    assert lead.processed_order_id is None  # subscription_fixture has no orders yet
    assert lead.processed_by_user_id == user.id
    assert lead.processed_at is not None


def test_mark_lead_processed_with_subscription_with_orders(session, client_fixture):
    from app.services.wix_integration_service import mark_lead_processed
    from app.models.user import User
    from app.models.subscription import Subscription
    from app.models.order import Order
    import datetime as _dt

    # Create subscription with an order
    subscription = Subscription(
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
    order = Order(
        client_id=client_fixture.id,
        subscription_id=None,  # will be set after subscription is committed
        recipient_name='Х',
        recipient_phone='+380000000000',
        city='Київ',
        street='вул.',
        size='M',
        delivery_date=_dt.date.today(),
        for_whom='Дружина',
    )
    session.add(subscription)
    session.flush()  # get subscription.id
    order.subscription_id = subscription.id
    session.add(order)
    session.commit()

    lead = WixLead(wix_order_id='order-3', raw_payload={}, status='new')
    user = User(username='mgr3', email='mgr3@example.com', user_type='admin')
    user.set_password('x')
    session.add_all([lead, user])
    session.commit()

    mark_lead_processed(lead, subscription, user)

    assert lead.status == 'processed'
    assert lead.processed_subscription_id == subscription.id
    assert lead.processed_order_id == order.id  # subscription has an order
    assert lead.processed_by_user_id == user.id
    assert lead.processed_at is not None
