import json

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.messaging_channel import MessagingChannel
from app.models.messaging_channel_access import MessagingChannelAccess
from app.models.user import User
from app.services.messaging import inbox_service
from app.services.messaging.adapter import InboundEvent, SentResult


def _channel(session, **kw):
    kw.setdefault('external_id', 'BC1')
    ch = MessagingChannel(name='TG', channel_type='telegram', webhook_secret='x', **kw)
    session.add(ch)
    session.commit()
    return ch


def _manager(session, username='mgr'):
    u = User(username=username, email=f'{username}@x.com', user_type='manager', is_active=True)
    u.set_password('p')
    session.add(u)
    session.commit()
    return u


def _msg_event(chat='555', mid='1', text='hi', media=None):
    return InboundEvent(kind='message', external_chat_id=chat, external_message_id=mid,
                        text=text, contact={'name': 'Ann', 'username': 'ann'},
                        media=media or [])


def test_ingest_creates_conversation_and_message(session):
    ch = _channel(session)
    msg = inbox_service.ingest_event(ch, _msg_event())
    assert msg is not None
    conv = Conversation.query.one()
    assert conv.channel_id == ch.id
    assert conv.external_chat_id == '555'
    assert conv.unread_count == 1
    assert conv.last_message_preview == 'hi'
    assert conv.last_message_direction == 'in'
    assert conv.contact_username == 'ann'


def test_ingest_second_message_increments_unread_same_conversation(session):
    ch = _channel(session)
    inbox_service.ingest_event(ch, _msg_event(mid='1'))
    inbox_service.ingest_event(ch, _msg_event(mid='2', text='again'))
    assert Conversation.query.count() == 1
    assert Conversation.query.one().unread_count == 2
    assert Message.query.count() == 2


def test_ingest_preserves_adapter_specific_media_keys(session):
    ch = _channel(session)
    media = [{'type': 'photo', 'tg_chat_id': 555, 'tg_message_id': 42, 'mime': 'image/jpeg', 'filename': None}]
    msg = inbox_service.ingest_event(ch, _msg_event(text=None, media=media))
    assert msg.media[0]['tg_chat_id'] == 555
    assert msg.media[0]['tg_message_id'] == 42
    assert msg.media[0]['path'] is None


def test_list_conversations_unread_only(session):
    ch = _channel(session)
    inbox_service.ingest_event(ch, _msg_event(chat='1', mid='1'))
    inbox_service.ingest_event(ch, _msg_event(chat='2', mid='2'))
    mgr = _manager(session)
    session.add(MessagingChannelAccess(channel_id=ch.id, user_id=mgr.id))
    session.commit()
    conv2 = Conversation.query.filter_by(external_chat_id='2').one()
    inbox_service.mark_read(conv2)

    all_convs = inbox_service.list_conversations(mgr)
    unread_convs = inbox_service.list_conversations(mgr, unread_only=True)
    assert len(all_convs) == 2
    assert [c.external_chat_id for c in unread_convs] == ['1']


def test_connection_event_updates_channel(session):
    ch = _channel(session, external_id=None, is_active=False)
    inbox_service.ingest_event(ch, InboundEvent(kind='connection', connection_id='BC9',
                                                connection_enabled=True))
    session.refresh(ch)
    assert ch.external_id == 'BC9'
    assert ch.is_active is True


def test_deleted_event_marks_messages(session):
    ch = _channel(session)
    inbox_service.ingest_event(ch, _msg_event(mid='11'))
    inbox_service.ingest_event(ch, InboundEvent(
        kind='deleted', external_chat_id='555', deleted_message_ids=['11']))
    assert Message.query.one().status == 'deleted'


def test_send_reply_persists_and_clears_unread(session, monkeypatch):
    ch = _channel(session)
    inbox_service.ingest_event(ch, _msg_event())
    conv = Conversation.query.one()
    user = _manager(session)

    monkeypatch.setattr(
        'app.services.messaging.telegram_business.TelegramBusinessAdapter.send_text',
        lambda self, channel, chat_id, text: SentResult(ok=True, external_message_id='out-1'),
    )
    msg = inbox_service.send_reply(conv, user, 'дякую за звернення')
    assert msg.direction == 'out'
    assert msg.status == 'sent'
    assert msg.sender_user_id == user.id
    session.refresh(conv)
    assert conv.unread_count == 0
    assert conv.last_message_direction == 'out'


def test_send_reply_failure_records_error(session, monkeypatch):
    ch = _channel(session)
    inbox_service.ingest_event(ch, _msg_event())
    conv = Conversation.query.one()
    monkeypatch.setattr(
        'app.services.messaging.telegram_business.TelegramBusinessAdapter.send_text',
        lambda self, channel, chat_id, text: SentResult(ok=False, error='BUSINESS_CONNECTION_INVALID'),
    )
    msg = inbox_service.send_reply(conv, _manager(session), 'hi')
    assert msg.status == 'failed'
    assert 'BUSINESS_CONNECTION_INVALID' in msg.error


def test_access_filtering(session):
    ch1 = _channel(session)
    ch2 = MessagingChannel(name='TG2', channel_type='telegram', webhook_secret='y')
    session.add(ch2)
    session.commit()
    inbox_service.ingest_event(ch1, _msg_event(chat='1'))
    inbox_service.ingest_event(ch2, _msg_event(chat='2'))

    mgr = _manager(session, 'limited')
    session.add(MessagingChannelAccess(channel_id=ch1.id, user_id=mgr.id))
    session.commit()

    convs = inbox_service.list_conversations(mgr)
    assert {c.channel_id for c in convs} == {ch1.id}
    assert inbox_service.total_unread(mgr) == 1


def test_admin_sees_all_channels(session):
    ch = _channel(session)
    inbox_service.ingest_event(ch, _msg_event())
    admin = User(username='a', email='a@x.com', user_type='admin', is_active=True)
    admin.set_password('p')
    session.add(admin)
    session.commit()
    assert ch.id in inbox_service.accessible_channel_ids(admin)


def test_webhook_route_rejects_bad_secret(app, session):
    ch = _channel(session)
    client = app.test_client()
    resp = client.post(f'/api/messaging/telegram/{ch.id}/webhook',
                       data=json.dumps({'business_message': {}}),
                       headers={'X-Telegram-Bot-Api-Secret-Token': 'nope'},
                       content_type='application/json')
    assert resp.status_code == 401


def test_instagram_ingest_learns_account_id(session):
    ch = MessagingChannel(name='IG', channel_type='instagram', webhook_secret='v', external_id=None)
    session.add(ch)
    session.commit()
    ev = InboundEvent(kind='message', external_chat_id='IGSID1', external_message_id='m1',
                      text='hi', contact={'_account_id': 'IGACC'}, media=[])
    inbox_service.ingest_event(ch, ev)
    session.refresh(ch)
    assert ch.external_id == 'IGACC'
    assert Conversation.query.one().external_chat_id == 'IGSID1'


def test_instagram_webhook_get_handshake(app, session):
    ch = MessagingChannel(name='IG', channel_type='instagram', webhook_secret='v-token')
    session.add(ch)
    session.commit()
    client = app.test_client()
    resp = client.get(f'/api/messaging/instagram/{ch.id}/webhook'
                      '?hub.mode=subscribe&hub.verify_token=v-token&hub.challenge=abc123')
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == 'abc123'
    bad = client.get(f'/api/messaging/instagram/{ch.id}/webhook'
                     '?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=abc123')
    assert bad.status_code == 403


def test_telegram_webhook_rejects_instagram_channel(app, session):
    ch = MessagingChannel(name='IG', channel_type='instagram', webhook_secret='v')
    session.add(ch)
    session.commit()
    resp = app.test_client().post(f'/api/messaging/telegram/{ch.id}/webhook',
                                  json={}, headers={'X-Telegram-Bot-Api-Secret-Token': 'v'})
    assert resp.status_code == 404


def test_webhook_route_ingests_with_valid_secret(app, session):
    ch = _channel(session)
    client = app.test_client()
    payload = {'business_message': {
        'message_id': 1, 'chat': {'id': 42}, 'from': {'id': 42, 'first_name': 'Z'},
        'text': 'hello from webhook',
    }}
    resp = client.post(f'/api/messaging/telegram/{ch.id}/webhook',
                       data=json.dumps(payload),
                       headers={'X-Telegram-Bot-Api-Secret-Token': 'x'},
                       content_type='application/json')
    assert resp.status_code == 200
    assert Message.query.count() == 1
    assert Conversation.query.one().last_message_preview == 'hello from webhook'
