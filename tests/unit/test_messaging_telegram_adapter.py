"""TelegramBusinessAdapter.parse_events + verify_webhook."""
from types import SimpleNamespace

from app.services.messaging.telegram_business import TelegramBusinessAdapter

adapter = TelegramBusinessAdapter()


def _headers(value):
    return SimpleNamespace(headers={'X-Telegram-Bot-Api-Secret-Token': value})


def test_verify_webhook_matches_secret():
    ch = SimpleNamespace(webhook_secret='s3cr3t')
    assert adapter.verify_webhook(_headers('s3cr3t'), ch) is True
    assert adapter.verify_webhook(_headers('wrong'), ch) is False
    assert adapter.verify_webhook(SimpleNamespace(headers={}), ch) is False


def test_parse_business_connection():
    events = adapter.parse_events({'business_connection': {'id': 'BC123', 'is_enabled': True}})
    assert len(events) == 1
    assert events[0].kind == 'connection'
    assert events[0].connection_id == 'BC123'
    assert events[0].connection_enabled is True


def test_parse_text_business_message():
    payload = {'business_message': {
        'message_id': 42,
        'business_connection_id': 'BC123',
        'date': 1_700_000_000,
        'chat': {'id': 987654321},
        'from': {'id': 987654321, 'first_name': 'Оля', 'username': 'olya'},
        'text': 'Привіт, хочу букет',
    }}
    events = adapter.parse_events(payload)
    assert len(events) == 1
    e = events[0]
    assert e.kind == 'message'
    assert e.external_chat_id == '987654321'
    assert e.external_message_id == '42'
    assert e.text == 'Привіт, хочу букет'
    assert e.contact['username'] == 'olya'
    assert e.contact['name'] == 'Оля'
    assert e.media == []
    assert e.date is not None


def test_parse_photo_message_collects_largest():
    payload = {'business_message': {
        'message_id': 7, 'chat': {'id': 1}, 'from': {'id': 1},
        'caption': 'ось референс',
        'photo': [
            {'file_id': 'small', 'file_size': 100},
            {'file_id': 'big', 'file_size': 9000},
        ],
    }}
    e = adapter.parse_events(payload)[0]
    assert e.text == 'ось референс'
    assert len(e.media) == 1
    assert e.media[0]['tg_file_id'] == 'big'
    assert e.media[0]['type'] == 'photo'


def test_parse_deleted_messages():
    payload = {'deleted_business_messages': {
        'business_connection_id': 'BC', 'chat': {'id': 5}, 'message_ids': [1, 2, 3],
    }}
    e = adapter.parse_events(payload)[0]
    assert e.kind == 'deleted'
    assert e.deleted_message_ids == ['1', '2', '3']
    assert e.external_chat_id == '5'


def test_parse_unknown_update_returns_empty():
    assert adapter.parse_events({'message': {'text': 'courier bot stuff'}}) == []


# ── telegram_personal: contact from the resolved sender ───────────────────

def _tg_message(**kw):
    from types import SimpleNamespace
    from datetime import datetime
    kw.setdefault('chat_id', 321803091)
    kw.setdefault('id', 7)
    kw.setdefault('message', 'привіт')
    kw.setdefault('photo', None)
    kw.setdefault('document', None)
    kw.setdefault('grouped_id', None)
    kw.setdefault('out', False)
    kw.setdefault('date', datetime(2026, 9, 22, 8, 0))
    return SimpleNamespace(**kw)


def _tg_peer(**kw):
    from types import SimpleNamespace
    kw.setdefault('first_name', 'Оксана')
    kw.setdefault('last_name', 'П')
    kw.setdefault('username', 'oksana_tg')
    kw.setdefault('phone', '380991112233')
    kw.setdefault('access_hash', 998877)
    return SimpleNamespace(**kw)


def test_build_inbound_event_takes_contact_from_peer():
    from app.services.messaging.telegram_personal import build_inbound_event

    ev = build_inbound_event(_tg_message(), peer=_tg_peer())
    assert ev.external_chat_id == '321803091'
    assert ev.contact == {'name': 'Оксана П', 'username': 'oksana_tg', 'phone': '380991112233'}
    assert ev.outgoing is False


def test_build_inbound_event_without_peer_has_empty_contact():
    from app.services.messaging.telegram_personal import build_inbound_event

    assert build_inbound_event(_tg_message()).contact == {}


def test_build_inbound_event_marks_own_messages_outgoing():
    from app.services.messaging.telegram_personal import build_inbound_event

    assert build_inbound_event(_tg_message(out=True)).outgoing is True


def test_media_carries_access_hash_and_album_id():
    from app.services.messaging.telegram_personal import build_inbound_event

    ev = build_inbound_event(_tg_message(photo=object(), grouped_id=123456),
                             peer=_tg_peer())
    assert ev.group_id == '123456'
    assert ev.media[0]['tg_access_hash'] == 998877
    assert ev.media[0]['tg_group_id'] == '123456'
    assert ev.media[0]['tg_message_id'] == 7


def test_resolve_peer_uses_stored_access_hash_without_touching_the_network():
    """An access hash in the media ref is exactly what spares a freshly
    connected client the entity lookup that used to raise ValueError."""
    import asyncio
    from telethon.tl.types import InputPeerUser
    from app.services.messaging.telegram_personal import TelegramPersonalAdapter

    class _Client:
        async def get_dialogs(self):
            raise AssertionError('should not need the dialog list')

    peer = asyncio.run(TelegramPersonalAdapter()._resolve_peer(
        _Client(), {'tg_chat_id': 321803091, 'tg_access_hash': 998877}))
    assert peer == InputPeerUser(321803091, 998877)


def test_resolve_peer_primes_the_cache_when_no_hash_was_stored():
    import asyncio
    from app.services.messaging.telegram_personal import TelegramPersonalAdapter

    calls = []

    class _Client:
        async def get_dialogs(self):
            calls.append(1)

    peer = asyncio.run(TelegramPersonalAdapter()._resolve_peer(
        _Client(), {'tg_chat_id': 321803091}))
    assert peer == 321803091
    assert calls == [1]


def test_enrich_contact_is_noop_inside_a_running_loop(recwarn):
    """The worker and the backfill already run in a loop — asyncio.run can't
    nest there, and the old code leaked a never-awaited coroutine."""
    import asyncio
    from app.services.messaging.telegram_personal import TelegramPersonalAdapter

    async def call():
        return TelegramPersonalAdapter().enrich_contact(object(), '123')

    assert asyncio.run(call()) == {}
    assert not [w for w in recwarn if issubclass(w.category, RuntimeWarning)]
