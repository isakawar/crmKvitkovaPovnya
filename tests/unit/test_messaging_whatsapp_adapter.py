import hashlib
import hmac
from types import SimpleNamespace

from app.services.messaging import session_crypto
from app.services.messaging.whatsapp import WhatsAppAdapter

adapter = WhatsAppAdapter()


def _channel(secret='vtok', wa_access_token_encrypted=None, external_id=None, wa_waba_id=None):
    return SimpleNamespace(webhook_secret=secret, external_id=external_id, channel_type='whatsapp',
                            wa_waba_id=wa_waba_id, wa_access_token_encrypted=wa_access_token_encrypted)


def _fernet_key():
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


def _connected_channel(app):
    app.config['MESSAGING_SESSION_KEY'] = _fernet_key()
    token = session_crypto.encrypt('wa-token-123')
    return _channel(wa_access_token_encrypted=token, external_id='PHONE_ID_1', wa_waba_id='WABA_1')


def test_verify_subscription_ok_and_bad():
    ch = _channel()
    args = {'hub.mode': 'subscribe', 'hub.verify_token': 'vtok', 'hub.challenge': '999'}
    assert adapter.verify_subscription(args, ch) == '999'
    args['hub.verify_token'] = 'nope'
    assert adapter.verify_subscription(args, ch) is None


def test_verify_webhook_signature(app):
    app.config['INBOX_INSTAGRAM_APP_SECRET'] = 'app-secret'
    body = b'{"hello":"world"}'
    good = 'sha256=' + hmac.new(b'app-secret', body, hashlib.sha256).hexdigest()
    req_ok = SimpleNamespace(headers={'X-Hub-Signature-256': good}, get_data=lambda: body)
    req_bad = SimpleNamespace(headers={'X-Hub-Signature-256': 'sha256=deadbeef'}, get_data=lambda: body)
    assert adapter.verify_webhook(req_ok, _channel()) is True
    assert adapter.verify_webhook(req_bad, _channel()) is False


def test_parse_text_message():
    payload = {
        'object': 'whatsapp_business_account',
        'entry': [{
            'id': 'WABA_1',
            'changes': [{
                'field': 'messages',
                'value': {
                    'messaging_product': 'whatsapp',
                    'contacts': [{'profile': {'name': 'Оксана'}, 'wa_id': '380991112233'}],
                    'messages': [{'from': '380991112233', 'id': 'wamid.1', 'type': 'text',
                                  'text': {'body': 'є букети на завтра?'}}],
                },
            }],
        }],
    }
    events = adapter.parse_events(payload)
    assert len(events) == 1
    e = events[0]
    assert e.external_chat_id == '380991112233'
    assert e.external_message_id == 'wamid.1'
    assert e.text == 'є букети на завтра?'
    assert e.contact == {'name': 'Оксана', 'phone': '380991112233'}


def test_parse_skips_status_updates():
    payload = {'object': 'whatsapp_business_account', 'entry': [{'id': 'WABA_1', 'changes': [{
        'field': 'statuses', 'value': {'statuses': [{'id': 'wamid.1', 'status': 'delivered'}]},
    }]}]}
    assert adapter.parse_events(payload) == []


def test_parse_image_message():
    payload = {'object': 'whatsapp_business_account', 'entry': [{'id': 'WABA_1', 'changes': [{
        'field': 'messages', 'value': {
            'messages': [{'from': 'U', 'id': 'wamid.2', 'type': 'image',
                          'image': {'id': 'MEDIA_1', 'mime_type': 'image/jpeg', 'caption': 'ось фото'}}],
        },
    }]}]}
    e = adapter.parse_events(payload)[0]
    assert e.media == [{'type': 'photo', 'media_id': 'MEDIA_1', 'mime': 'image/jpeg', 'filename': None}]
    assert e.text == 'ось фото'


def test_parse_ignores_non_whatsapp_object():
    assert adapter.parse_events({'object': 'page', 'entry': []}) == []


def test_send_text_requires_connected_channel():
    res = adapter.send_text(_channel(), 'U', 'привіт')
    assert res.ok is False
    assert 'перепідключіть' in res.error


def test_send_text_uses_token_and_phone_number_id(app, monkeypatch):
    ch = _connected_channel(app)
    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls['url'] = url
        calls['headers'] = headers
        calls['json'] = json
        return SimpleNamespace(status_code=200, json=lambda: {'messages': [{'id': 'wamid.out.1'}]})

    monkeypatch.setattr('app.services.messaging.whatsapp.requests.post', fake_post)
    res = adapter.send_text(ch, '380991112233', 'привіт')
    assert res.ok is True
    assert res.external_message_id == 'wamid.out.1'
    assert calls['url'].endswith('/PHONE_ID_1/messages')
    assert calls['headers'] == {'Authorization': 'Bearer wa-token-123'}
    assert calls['json'] == {'messaging_product': 'whatsapp', 'to': '380991112233',
                              'type': 'text', 'text': {'body': 'привіт'}}


def test_register_webhook_subscribes_waba(app, monkeypatch):
    ch = _connected_channel(app)
    calls = {}

    def fake_post(url, headers=None, timeout=None):
        calls['url'] = url
        return SimpleNamespace(status_code=200, json=lambda: {'success': True})

    monkeypatch.setattr('app.services.messaging.whatsapp.requests.post', fake_post)
    adapter.register_webhook(ch, 'https://crm.example/webhook')  # must not raise
    assert calls['url'].endswith('/WABA_1/subscribed_apps')


def _jpeg_file(tmp_path, name='photo.jpg', color='red'):
    from PIL import Image
    path = tmp_path / name
    Image.new('RGB', (4, 4), color=color).save(path, format='JPEG')
    return str(path)


def test_send_media_requires_connected_channel(tmp_path):
    res = adapter.send_media(_channel(), 'U', _jpeg_file(tmp_path))
    assert res.ok is False
    assert 'перепідключіть' in res.error


def test_send_media_uploads_then_sends(app, monkeypatch, tmp_path):
    ch = _connected_channel(app)
    calls = []

    def fake_post(url, headers=None, data=None, files=None, json=None, timeout=None):
        calls.append({'url': url, 'headers': headers, 'data': data, 'files': files, 'json': json})
        if url.endswith('/media'):
            return SimpleNamespace(status_code=200, json=lambda: {'id': 'MEDIA_OUT_1'})
        return SimpleNamespace(status_code=200, json=lambda: {'messages': [{'id': 'wamid.out.2'}]})

    monkeypatch.setattr('app.services.messaging.whatsapp.requests.post', fake_post)
    res = adapter.send_media(ch, '380991112233', _jpeg_file(tmp_path), caption='ось букет')
    assert res.ok is True
    assert res.external_message_id == 'wamid.out.2'
    assert len(calls) == 2
    assert calls[0]['url'].endswith('/PHONE_ID_1/media')
    assert calls[0]['headers'] == {'Authorization': 'Bearer wa-token-123'}
    assert calls[1]['json'] == {'messaging_product': 'whatsapp', 'to': '380991112233',
                                 'type': 'image', 'image': {'id': 'MEDIA_OUT_1', 'caption': 'ось букет'}}


def test_send_media_fails_when_upload_errors(app, monkeypatch, tmp_path):
    ch = _connected_channel(app)

    def fake_post(url, headers=None, data=None, files=None, json=None, timeout=None):
        return SimpleNamespace(status_code=400, json=lambda: {'error': {'message': 'bad token'}})

    monkeypatch.setattr('app.services.messaging.whatsapp.requests.post', fake_post)
    res = adapter.send_media(ch, 'U', _jpeg_file(tmp_path))
    assert res.ok is False
    assert 'bad token' in res.error
