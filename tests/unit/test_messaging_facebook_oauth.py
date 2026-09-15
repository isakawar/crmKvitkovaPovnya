from types import SimpleNamespace

import pytest

from app.services.messaging import facebook_oauth as fbo


def _configure(app):
    app.config['FACEBOOK_APP_ID'] = 'app-id-1'
    app.config['INBOX_INSTAGRAM_APP_SECRET'] = 'app-secret-1'
    app.config['CRM_PUBLIC_URL'] = 'https://crm.example.com'


def test_authorize_url_contains_client_id_state_and_redirect(app):
    _configure(app)
    url = fbo.authorize_url('state-123')
    assert 'client_id=app-id-1' in url
    assert 'state=state-123' in url
    assert 'redirect_uri=https%3A%2F%2Fcrm.example.com%2Fsettings%2Fmessaging%2Ffacebook%2Fcallback' in url
    assert 'instagram_manage_messages' in url


def test_authorize_url_requires_public_url(app):
    app.config['FACEBOOK_APP_ID'] = 'app-id-1'
    app.config['INBOX_INSTAGRAM_APP_SECRET'] = 'app-secret-1'
    app.config['CRM_PUBLIC_URL'] = ''
    with pytest.raises(RuntimeError):
        fbo.authorize_url('state-123')


def test_exchange_code_for_user_token(app, monkeypatch):
    _configure(app)

    def fake_get(url, params=None, timeout=None):
        assert params['code'] == 'abc'
        return SimpleNamespace(status_code=200, json=lambda: {'access_token': 'short-token'})

    monkeypatch.setattr('app.services.messaging.facebook_oauth.requests.get', fake_get)
    assert fbo.exchange_code_for_user_token('abc') == 'short-token'


def test_exchange_code_for_user_token_error(app, monkeypatch):
    _configure(app)

    def fake_get(url, params=None, timeout=None):
        return SimpleNamespace(status_code=400, json=lambda: {'error': {'message': 'bad code'}})

    monkeypatch.setattr('app.services.messaging.facebook_oauth.requests.get', fake_get)
    with pytest.raises(RuntimeError, match='bad code'):
        fbo.exchange_code_for_user_token('abc')


def test_exchange_long_lived_token(app, monkeypatch):
    _configure(app)

    def fake_get(url, params=None, timeout=None):
        assert params['grant_type'] == 'fb_exchange_token'
        return SimpleNamespace(status_code=200, json=lambda: {'access_token': 'long-token'})

    monkeypatch.setattr('app.services.messaging.facebook_oauth.requests.get', fake_get)
    assert fbo.exchange_long_lived_token('short-token') == 'long-token'


def test_list_connected_pages_skips_pages_without_instagram(app, monkeypatch):
    _configure(app)

    def fake_get(url, params=None, timeout=None):
        return SimpleNamespace(status_code=200, json=lambda: {'data': [
            {'id': 'PAGE_1', 'name': 'Квіткова Повня', 'access_token': 'page-tok-1',
             'instagram_business_account': {'id': 'IG_1', 'username': 'kvitkova'}},
            {'id': 'PAGE_2', 'name': 'No IG Page', 'access_token': 'page-tok-2'},
        ]})

    monkeypatch.setattr('app.services.messaging.facebook_oauth.requests.get', fake_get)
    pages = fbo.list_connected_pages('long-token')
    assert len(pages) == 1
    assert pages[0] == {
        'page_id': 'PAGE_1', 'page_name': 'Квіткова Повня',
        'page_access_token': 'page-tok-1', 'ig_id': 'IG_1', 'ig_username': 'kvitkova',
    }
