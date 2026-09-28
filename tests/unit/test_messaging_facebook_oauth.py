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
    assert 'pages_read_engagement' in url


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


def test_list_connected_pages_names_pages_when_none_has_instagram(app, monkeypatch):
    _configure(app)

    def fake_get(url, params=None, timeout=None):
        return SimpleNamespace(status_code=200, json=lambda: {'data': [
            {'id': 'PAGE_2', 'name': 'dariamitr', 'access_token': 'page-tok-2'},
        ]})

    monkeypatch.setattr('app.services.messaging.facebook_oauth.requests.get', fake_get)
    with pytest.raises(fbo.NoInstagramPagesError, match='dariamitr'):
        fbo.list_connected_pages('long-token')


def test_list_connected_pages_no_pages_granted(app, monkeypatch):
    _configure(app)

    def fake_get(url, params=None, timeout=None):
        return SimpleNamespace(status_code=200, json=lambda: {'data': []})

    monkeypatch.setattr('app.services.messaging.facebook_oauth.requests.get', fake_get)
    with pytest.raises(fbo.NoInstagramPagesError, match='не повернув жодної сторінки'):
        fbo.list_connected_pages('long-token')


def test_list_connected_pages_logs_granted_assets_when_empty(app, monkeypatch, caplog):
    _configure(app)
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        if url.endswith('/debug_token'):
            assert params['access_token'] == 'app-id-1|app-secret-1'
            return SimpleNamespace(status_code=200, json=lambda: {'data': {'granular_scopes': [
                {'scope': 'pages_show_list', 'target_ids': ['PAGE_9']},
                {'scope': 'instagram_basic', 'target_ids': ['IG_9']},
            ]}})
        return SimpleNamespace(status_code=200, json=lambda: {'data': []})

    monkeypatch.setattr('app.services.messaging.facebook_oauth.requests.get', fake_get)
    with pytest.raises(fbo.NoInstagramPagesError):
        fbo.list_connected_pages('long-token')
    assert any(u.endswith('/debug_token') for u in calls)
    assert 'PAGE_9' in caplog.text and 'IG_9' in caplog.text


def _fake_graph(debug_scopes, pages_by_id):
    """/me/accounts empty; debug_token returns `debug_scopes`; /{page_id}
    returns pages_by_id[page_id] or a Graph error."""
    def fake_get(url, params=None, timeout=None):
        if url.endswith('/me/accounts'):
            return SimpleNamespace(status_code=200, json=lambda: {'data': []})
        if url.endswith('/debug_token'):
            return SimpleNamespace(status_code=200, json=lambda: {'data': {'granular_scopes': debug_scopes}})
        page_id = url.rsplit('/', 1)[-1]
        if page_id in pages_by_id:
            return SimpleNamespace(status_code=200, json=lambda: pages_by_id[page_id])
        return SimpleNamespace(status_code=400, json=lambda: {'error': {'message': 'no access'}})
    return fake_get


def test_list_connected_pages_falls_back_to_granted_page_ids(app, monkeypatch):
    _configure(app)
    monkeypatch.setattr('app.services.messaging.facebook_oauth.requests.get', _fake_graph(
        [{'scope': 'pages_show_list', 'target_ids': ['PAGE_9']},
         {'scope': 'pages_messaging', 'target_ids': ['PAGE_9']},
         {'scope': 'instagram_basic', 'target_ids': ['IG_9']}],
        {'PAGE_9': {'id': 'PAGE_9', 'name': 'dariamitr', 'access_token': 'page-tok-9',
                    'instagram_business_account': {'id': 'IG_9', 'username': 'kvitkova.povnya'}}},
    ))
    pages = fbo.list_connected_pages('long-token')
    assert pages == [{
        'page_id': 'PAGE_9', 'page_name': 'dariamitr',
        'page_access_token': 'page-tok-9', 'ig_id': 'IG_9', 'ig_username': 'kvitkova.povnya',
    }]


def test_list_connected_pages_fallback_page_without_token(app, monkeypatch):
    _configure(app)
    monkeypatch.setattr('app.services.messaging.facebook_oauth.requests.get', _fake_graph(
        [{'scope': 'pages_show_list', 'target_ids': ['PAGE_9']}],
        {'PAGE_9': {'id': 'PAGE_9', 'name': 'dariamitr',
                    'instagram_business_account': {'id': 'IG_9', 'username': 'kvitkova.povnya'}}},
    ))
    with pytest.raises(fbo.NoInstagramPagesError, match='Немає дозволу керувати повідомленнями сторінки \\(dariamitr\\)'):
        fbo.list_connected_pages('long-token')


def test_list_connected_pages_fallback_page_fetch_error(app, monkeypatch):
    _configure(app)
    monkeypatch.setattr('app.services.messaging.facebook_oauth.requests.get', _fake_graph(
        [{'scope': 'pages_show_list', 'target_ids': ['PAGE_9']}], {},
    ))
    with pytest.raises(fbo.NoInstagramPagesError, match='PAGE_9: no access'):
        fbo.list_connected_pages('long-token')


def test_list_connected_pages_all_pages_granted_asks_to_pick_specific(app, monkeypatch):
    _configure(app)
    monkeypatch.setattr('app.services.messaging.facebook_oauth.requests.get', _fake_graph(
        [{'scope': 'pages_show_list'}, {'scope': 'instagram_basic'}], {},
    ))
    with pytest.raises(fbo.NoInstagramPagesError, match='відмітьте потрібну сторінку конкретно'):
        fbo.list_connected_pages('long-token')
