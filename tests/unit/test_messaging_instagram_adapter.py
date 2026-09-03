import hashlib
import hmac
import json
from types import SimpleNamespace

from app.services.messaging.instagram_dm import InstagramDMAdapter

adapter = InstagramDMAdapter()


def _channel(secret='vtok'):
    return SimpleNamespace(webhook_secret=secret, external_id=None, channel_type='instagram')


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
