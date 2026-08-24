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
