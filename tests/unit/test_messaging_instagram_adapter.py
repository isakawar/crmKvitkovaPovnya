import hashlib
import hmac
import json
from types import SimpleNamespace

from app.services.messaging import session_crypto
from app.services.messaging.instagram_dm import InstagramDMAdapter

adapter = InstagramDMAdapter()


def _channel(secret='vtok', fb_page_access_token_encrypted=None, external_id=None, fb_page_id=None):
    return SimpleNamespace(webhook_secret=secret, external_id=external_id, channel_type='instagram',
                            fb_page_id=fb_page_id, fb_page_access_token_encrypted=fb_page_access_token_encrypted)


def _connected_channel(app):
    app.config['MESSAGING_SESSION_KEY'] = _fernet_key()
    token = session_crypto.encrypt('page-token-123')
    return _channel(fb_page_access_token_encrypted=token, external_id='IG_ACCOUNT_1', fb_page_id='PAGE_1')


def _fernet_key():
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


def test_verify_subscription_ok_and_bad():
    ch = _channel()
    args = {'hub.mode': 'subscribe', 'hub.verify_token': 'vtok', 'hub.challenge': '12345'}
    assert adapter.verify_subscription(args, ch) == '12345'
    args['hub.verify_token'] = 'nope'
    assert adapter.verify_subscription(args, ch) is None
    assert adapter.verify_subscription({}, ch) is None


def test_verify_webhook_signature(app, monkeypatch):
    monkeypatch.setitem(app.config, 'INBOX_INSTAGRAM_APP_SECRET', 'app-secret')
    body = b'{"hello":"world"}'
    good = 'sha256=' + hmac.new(b'app-secret', body, hashlib.sha256).hexdigest()
    req_ok = SimpleNamespace(headers={'X-Hub-Signature-256': good}, get_data=lambda: body)
    req_bad = SimpleNamespace(headers={'X-Hub-Signature-256': 'sha256=deadbeef'}, get_data=lambda: body)
    assert adapter.verify_webhook(req_ok, _channel()) is True
    assert adapter.verify_webhook(req_bad, _channel()) is False


def test_parse_text_message():
    payload = {
        'object': 'instagram',
        'entry': [{
            'id': 'IG_ACCOUNT_1',
            'messaging': [{
                'sender': {'id': 'IGSID_9'},
                'recipient': {'id': 'IG_ACCOUNT_1'},
                'message': {'mid': 'm_1', 'text': 'є букети на завтра?'},
            }],
        }],
    }
    events = adapter.parse_events(payload)
    assert len(events) == 1
    e = events[0]
    assert e.external_chat_id == 'IGSID_9'
    assert e.external_message_id == 'm_1'
    assert e.text == 'є букети на завтра?'
    assert e.contact['_account_id'] == 'IG_ACCOUNT_1'


def test_parse_skips_echo():
    payload = {'object': 'instagram', 'entry': [{'id': 'A', 'messaging': [
        {'sender': {'id': 'A'}, 'message': {'mid': 'x', 'text': 'ours', 'is_echo': True}},
    ]}]}
    assert adapter.parse_events(payload) == []


def test_parse_attachment():
    payload = {'object': 'instagram', 'entry': [{'id': 'A', 'messaging': [{
        'sender': {'id': 'U'},
        'message': {'mid': 'x', 'attachments': [
            {'type': 'image', 'payload': {'url': 'https://cdn.example/pic.jpg'}}]},
    }]}]}
    e = adapter.parse_events(payload)[0]
    assert e.media == [{'type': 'photo', 'url': 'https://cdn.example/pic.jpg',
                        'mime': None, 'filename': None}]


def test_parse_ignores_non_instagram_object():
    assert adapter.parse_events({'object': 'page', 'entry': []}) == []


def test_send_media_not_supported():
    res = adapter.send_media(_channel(), 'U', '/tmp/x.jpg')
    assert res.ok is False


def test_send_text_requires_connected_channel():
    res = adapter.send_text(_channel(), 'U', 'hi')
    assert res.ok is False
    assert 'перепідключіть' in res.error


def test_send_text_uses_page_token_and_ig_account(app, monkeypatch):
    ch = _connected_channel(app)
    calls = {}

    def fake_post(url, params=None, json=None, timeout=None):
        calls['url'] = url
        calls['params'] = params
        calls['json'] = json
        return SimpleNamespace(status_code=200, json=lambda: {'message_id': 'mid_1'})

    monkeypatch.setattr('app.services.messaging.instagram_dm.requests.post', fake_post)
    res = adapter.send_text(ch, 'IGSID_9', 'привіт')
    assert res.ok is True
    assert res.external_message_id == 'mid_1'
    assert calls['url'].endswith('/IG_ACCOUNT_1/messages')
    assert calls['params']['access_token'] == 'page-token-123'
    assert calls['json'] == {'recipient': {'id': 'IGSID_9'}, 'message': {'text': 'привіт'}}


def test_register_webhook_subscribes_page(app, monkeypatch):
    ch = _connected_channel(app)
    calls = {}

    def fake_post(url, params=None, timeout=None):
        calls['url'] = url
        calls['params'] = params
        return SimpleNamespace(status_code=200, json=lambda: {'success': True})

    monkeypatch.setattr('app.services.messaging.instagram_dm.requests.post', fake_post)
    adapter.register_webhook(ch, 'https://crm.example/webhook')  # must not raise
    assert calls['url'].endswith('/PAGE_1/subscribed_apps')
    assert calls['params']['subscribed_fields'] == 'messages'


def test_register_webhook_raises_on_error(app, monkeypatch):
    ch = _connected_channel(app)

    def fake_post(url, params=None, timeout=None):
        return SimpleNamespace(status_code=400, json=lambda: {'error': {'message': 'boom'}})

    monkeypatch.setattr('app.services.messaging.instagram_dm.requests.post', fake_post)
    try:
        adapter.register_webhook(ch, 'https://crm.example/webhook')
        assert False, 'expected RuntimeError'
    except RuntimeError as exc:
        assert 'boom' in str(exc)
