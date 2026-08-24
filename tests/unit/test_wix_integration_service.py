from app.models.wix_lead import WixLead
from app.models.wix_product_mapping import WixProductMapping


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
