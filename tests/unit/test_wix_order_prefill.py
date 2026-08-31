from app.models.wix_lead import WixLead
from app.models.wix_product_mapping import WixProductMapping
from app.models.user import User
from app.models import Client


def _login(app, client, user):
    with client.session_transaction() as flask_session:
        flask_session['_user_id'] = str(user.id)
        flask_session['_fresh'] = True


def _make_manager(session):
    user = User(username='mgr', email='mgr@example.com', user_type='manager', is_active=True)
    user.set_password('secret')
    session.add(user)
    session.commit()
    return user


def test_order_form_prefills_from_new_lead(app, session):
    manager = _make_manager(session)
    mapping = WixProductMapping(
        catalog_item_id='cat-1', order_scenario='subscription',
        delivery_type='Monthly', size='M',
    )
    lead = WixLead(
        wix_order_id='o-10', raw_payload={}, status='new',
        contact_name='Влад Білобров', contact_phone='+380666746225',
        city='Київ', street='вул. Зарічна, 1Г', catalog_item_id='cat-1',
        wix_order_number='10255', amount='6800.00', currency='UAH',
    )
    session.add_all([mapping, lead])
    session.commit()

    client = app.test_client()
    _login(app, client, manager)
    resp = client.get(f'/orders/new?lead_id={lead.id}')

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Влад Білобров' in html
    assert '+380666746225' in html
    assert 'вул. Зарічна, 1Г' in html
    assert '10255' in html


def test_order_form_ignores_already_processed_lead(app, session):
    manager = _make_manager(session)
    lead = WixLead(
        wix_order_id='o-11', raw_payload={}, status='processed',
        contact_name='Не Показувати',
    )
    session.add(lead)
    session.commit()

    client = app.test_client()
    _login(app, client, manager)
    resp = client.get(f'/orders/new?lead_id={lead.id}')

    assert resp.status_code == 200
    assert 'Не Показувати' not in resp.get_data(as_text=True)


def test_order_create_marks_lead_processed(app, session):
    manager = _make_manager(session)
    client_obj = Client(instagram='vlad_flowers', phone='+380666746225')
    lead = WixLead(wix_order_id='o-20', raw_payload={}, status='new')
    session.add_all([client_obj, lead])
    session.commit()

    web_client = app.test_client()
    _login(app, web_client, manager)

    resp = web_client.post('/orders/new', data={
        'lead_id': str(lead.id),
        'client_id': str(client_obj.id),
        'recipient_name': 'Влад Білобров',
        'recipient_phone': '+380666746225',
        'city': 'Київ',
        'street': 'вул. Зарічна, 1Г',
        'delivery_type': 'Разова',
        'delivery_method': 'courier',
        'size': 'M',
        'first_delivery_date': '2026-09-01',
        'for_whom': 'Дружина',
    }, follow_redirects=True)

    assert resp.status_code == 200
    updated = WixLead.query.get(lead.id)
    assert updated.status == 'processed'
    assert updated.processed_order_id is not None
    assert updated.processed_by_user_id == manager.id


def test_order_create_does_not_reprocess_already_processed_lead(app, session):
    manager = _make_manager(session)
    client_obj = Client(instagram='vlad_flowers', phone='+380666746225')
    lead = WixLead(
        wix_order_id='o-21', raw_payload={}, status='processed',
        processed_order_id=None,
    )
    session.add_all([client_obj, lead])
    session.commit()
    lead_id = lead.id

    web_client = app.test_client()
    _login(app, web_client, manager)

    resp = web_client.post('/orders/new', data={
        'lead_id': str(lead_id),
        'client_id': str(client_obj.id),
        'recipient_name': 'Влад Білобров',
        'recipient_phone': '+380666746225',
        'city': 'Київ',
        'street': 'вул. Зарічна, 1Г',
        'delivery_type': 'Разова',
        'delivery_method': 'courier',
        'size': 'M',
        'first_delivery_date': '2026-09-01',
        'for_whom': 'Дружина',
    }, follow_redirects=True)

    assert resp.status_code == 200
    updated = WixLead.query.get(lead_id)
    # Lead was already 'processed' (not 'new'), so order_create()'s
    # `if lead and lead.status == 'new'` guard must no-op - it must not get
    # reassigned to this new order.
    assert updated.status == 'processed'
    assert updated.processed_order_id is None


def test_wix_lead_composer_data_endpoint(app, session):
    manager = _make_manager(session)
    mapping = WixProductMapping(catalog_item_id='cat-sub', order_scenario='subscription',
                                delivery_type='Weekly', size='L')
    client_obj = Client(instagram='masha_flowers', phone='+380671112233')
    lead = WixLead(
        wix_order_id='o-cd-1', wix_order_number='9001', raw_payload={}, status='new',
        contact_name='Марія Н', contact_phone='+380671112233', city='Київ',
        street='вул. Тестова, 5', catalog_item_id='cat-sub', amount='6800.00', currency='UAH',
        buyer_note='без лілій',
        custom_fields={'periodichnist_dostavki': 'Щотижня', 'data_pershoyi_dostavki': '2026-09-10'},
    )
    session.add_all([mapping, client_obj, lead])
    session.commit()
    lead.matched_client_id = client_obj.id
    session.commit()

    web_client = app.test_client()
    _login(app, web_client, manager)
    resp = web_client.get(f'/orders/wix-lead/{lead.id}/composer-data')
    assert resp.status_code == 200
    d = resp.get_json()
    assert d['flow'] == 'subscription'
    assert d['size'] == 'L'
    assert d['delivery_type'] == 'Weekly'
    assert d['first_delivery_date'] == '2026-09-10'
    assert d['client_id'] == client_obj.id
    assert d['client_instagram'] == 'masha_flowers'
    assert 'без лілій' in d['preferences']
    assert d['wix_lead']['mapping_matched'] is True
    labels = [f['label'] for f in d['wix_lead']['custom_fields']]
    assert 'Періодичність доставки' in labels


def test_wix_lead_composer_data_rejects_processed(app, session):
    manager = _make_manager(session)
    lead = WixLead(wix_order_id='o-cd-2', raw_payload={}, status='processed')
    session.add(lead)
    session.commit()
    web_client = app.test_client()
    _login(app, web_client, manager)
    resp = web_client.get(f'/orders/wix-lead/{lead.id}/composer-data')
    assert resp.status_code == 409


def test_composer_data_live_matches_client_created_after_webhook(app, session):
    """matched_client_id was never set, but a client with the lead's phone exists now."""
    manager = _make_manager(session)
    lead = WixLead(
        wix_order_id='o-live-1', raw_payload={}, status='new',
        contact_name='Пізній Клієнт', contact_phone='+380631112244',
    )
    session.add(lead)
    session.commit()
    assert lead.matched_client_id is None

    # client created later, independently
    later = Client(instagram='late_client', phone='+380631112244')
    session.add(later)
    session.commit()

    web_client = app.test_client()
    _login(app, web_client, manager)
    d = web_client.get(f'/orders/wix-lead/{lead.id}/composer-data').get_json()
    assert d['client_id'] == later.id
    assert d['client_instagram'] == 'late_client'
    assert d['wix_lead']['client_matched'] is True
