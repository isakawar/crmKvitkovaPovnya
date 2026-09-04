import hashlib
import hmac
from types import SimpleNamespace

from app.services.messaging.viber import ViberAdapter

adapter = ViberAdapter()


def _channel():
    return SimpleNamespace(channel_type='viber', name='Kvitkova Povnya')


def test_verify_subscription_always_none():
    assert adapter.verify_subscription({}, _channel()) is None


def test_verify_webhook_signature(app):
    app.config['INBOX_VIBER_BOT_TOKEN'] = 'bot-token'
    body = b'{"event":"message"}'
    good = hmac.new(b'bot-token', body, hashlib.sha256).hexdigest()
    req_ok = SimpleNamespace(headers={'X-Viber-Content-Signature': good}, get_data=lambda: body)
    req_bad = SimpleNamespace(headers={'X-Viber-Content-Signature': 'deadbeef'}, get_data=lambda: body)
    assert adapter.verify_webhook(req_ok, _channel()) is True
    assert adapter.verify_webhook(req_bad, _channel()) is False


def test_parse_text_message():
    payload = {
        'event': 'message',
        'timestamp': 1457764197627,
        'message_token': 4912661846655238145,
        'sender': {'id': 'user-1', 'name': 'Ганна'},
        'message': {'type': 'text', 'text': 'є букети на завтра?'},
    }
    events = adapter.parse_events(payload)
    assert len(events) == 1
    e = events[0]
    assert e.external_chat_id == 'user-1'
    assert e.external_message_id == '4912661846655238145'
    assert e.text == 'є букети на завтра?'
    assert e.contact['name'] == 'Ганна'


def test_parse_picture_message():
    payload = {
        'event': 'message',
        'sender': {'id': 'user-1', 'name': 'Ганна'},
        'message': {'type': 'picture', 'text': 'ось фото', 'media': 'https://cdn.viber.com/pic.jpg'},
    }
    e = adapter.parse_events(payload)[0]
    assert e.media == [{'type': 'photo', 'url': 'https://cdn.viber.com/pic.jpg',
                        'mime': None, 'filename': None}]
    assert e.text == 'ось фото'


def test_parse_unsupported_type_gets_placeholder():
    payload = {'event': 'message', 'sender': {'id': 'u'}, 'message': {'type': 'sticker'}}
    e = adapter.parse_events(payload)[0]
    assert e.text == '[непідтримуваний тип повідомлення]'


def test_parse_ignores_non_message_events():
    assert adapter.parse_events({'event': 'subscribed', 'user': {'id': 'u'}}) == []
    assert adapter.parse_events({'event': 'delivered'}) == []


def test_send_media_not_supported():
    res = adapter.send_media(_channel(), 'user-1', '/tmp/x.jpg')
    assert res.ok is False
