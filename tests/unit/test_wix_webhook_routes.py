import copy
import json

from tests.unit.test_wix_integration_service import SAMPLE_WIX_PAYLOAD
from app.models.wix_lead import WixLead


def test_webhook_rejects_when_not_configured(app):
    app.config['WIX_ALLOWED_SITE_IDS'] = ''
    client = app.test_client()
    resp = client.post(
        '/api/integrations/wix/order-placed',
        data=json.dumps(SAMPLE_WIX_PAYLOAD),
        content_type='application/json',
    )
    assert resp.status_code == 503


def test_webhook_rejects_unknown_site(app):
    app.config['WIX_ALLOWED_SITE_IDS'] = 'some-other-site-id'
    client = app.test_client()
    resp = client.post(
        '/api/integrations/wix/order-placed',
        data=json.dumps(SAMPLE_WIX_PAYLOAD),
        content_type='application/json',
    )
    assert resp.status_code == 403


def test_webhook_accepts_known_site_and_creates_lead(app, session):
    app.config['WIX_ALLOWED_SITE_IDS'] = '2c31eac1-a4f1-4fd2-886d-361377a42a1f'
    client = app.test_client()
    resp = client.post(
        '/api/integrations/wix/order-placed',
        data=json.dumps(SAMPLE_WIX_PAYLOAD),
        content_type='application/json',
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    lead = WixLead.query.get(body['lead_id'])
    assert lead is not None
    assert lead.wix_order_id == '3521b3e3-cf2d-4093-9b77-b562f6f03165'


def test_webhook_rejects_invalid_json_body(app):
    app.config['WIX_ALLOWED_SITE_IDS'] = '2c31eac1-a4f1-4fd2-886d-361377a42a1f'
    client = app.test_client()
    resp = client.post(
        '/api/integrations/wix/order-placed',
        data='not json',
        content_type='application/json',
    )
    assert resp.status_code == 400


def test_webhook_is_public_no_login_required(app):
    """The require_login before_request hook must not redirect this endpoint."""
    app.config['WIX_ALLOWED_SITE_IDS'] = 'x'
    app.config['LOGIN_DISABLED'] = False
    client = app.test_client()
    resp = client.post(
        '/api/integrations/wix/order-placed',
        data=json.dumps({}),
        content_type='application/json',
    )
    assert resp.status_code != 302


from app.models.user import User


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


def test_leads_list_requires_admin_or_manager(app, session):
    florist = User(username='flo', email='flo@example.com', user_type='florist', is_active=True)
    florist.set_password('secret')
    session.add(florist)
    session.commit()

    client = app.test_client()
    _login(app, client, florist)
    resp = client.get('/integrations/wix-leads')
    assert resp.status_code == 403


def test_leads_list_shows_new_leads(app, session):
    manager = _make_manager(session)
    lead = WixLead(
        wix_order_id='o-1', wix_order_number='100', raw_payload={}, status='new',
        item_name='Підписка на квіти М (4 доставки)',
    )
    session.add(lead)
    session.commit()

    client = app.test_client()
    _login(app, client, manager)
    resp = client.get('/integrations/wix-leads')

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Підписка на квіти М (4 доставки)' in html


def test_ignore_lead_changes_status(app, session):
    manager = _make_manager(session)
    lead = WixLead(wix_order_id='o-2', raw_payload={}, status='new')
    session.add(lead)
    session.commit()

    client = app.test_client()
    _login(app, client, manager)
    resp = client.post(f'/integrations/wix-leads/{lead.id}/ignore', follow_redirects=True)

    assert resp.status_code == 200
    assert WixLead.query.get(lead.id).status == 'ignored'
