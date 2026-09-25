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
    kw.setdefault('channel_type', 'telegram')
    ch = MessagingChannel(name='TG', webhook_secret='x', **kw)
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


def _logged_in_client(app, session):
    """A test client authenticated as an admin (sees every channel, so
    _conversation_or_404's access check doesn't need per-channel grants
    for these route tests)."""
    admin = User(username='route_admin', email='route_admin@x.com', user_type='admin', is_active=True)
    admin.set_password('p')
    session.add(admin)
    session.commit()
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(admin.id)
        sess['_fresh'] = True
    return c


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


def test_ingest_ignores_redelivered_duplicate(session):
    ch = _channel(session)
    first = inbox_service.ingest_event(ch, _msg_event(mid='dup-1'))
    duplicate = inbox_service.ingest_event(ch, _msg_event(mid='dup-1', text='same message again'))
    assert first is not None
    assert duplicate is None
    conv = Conversation.query.one()
    assert Message.query.filter_by(conversation_id=conv.id).count() == 1
    assert conv.unread_count == 1


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


def _conv_with_messages(session, ch, n, texts=None):
    conv = Conversation(channel_id=ch.id, external_chat_id='555')
    session.add(conv)
    session.commit()
    for i in range(n):
        session.add(Message(conversation_id=conv.id, direction='in',
                            text=(texts[i] if texts else f'msg{i}')))
    session.commit()
    return conv


def test_get_thread_initial_page_is_chronological_not_reversed(session):
    # Regression: conversation.messages is a dynamic relationship with its
    # own baked-in `ORDER BY id ASC`; get_thread used to append `.desc()`
    # without resetting it first, which SQLAlchemy silently ignores (the
    # unique `id` column means the first ORDER BY clause wins outright) —
    # so it returned the OLDEST page, reversed, instead of the newest page
    # in chronological order.
    ch = _channel(session)
    conv = _conv_with_messages(session, ch, 5, texts=['a', 'b', 'c', 'd', 'e'])
    msgs, has_more = inbox_service.get_thread(conv, limit=3)
    assert [m.text for m in msgs] == ['c', 'd', 'e']  # newest 3, oldest-first
    assert has_more is True


def test_get_thread_no_pagination_needed_when_under_limit(session):
    ch = _channel(session)
    conv = _conv_with_messages(session, ch, 3, texts=['a', 'b', 'c'])
    msgs, has_more = inbox_service.get_thread(conv, limit=50)
    assert [m.text for m in msgs] == ['a', 'b', 'c']
    assert has_more is False


def test_get_thread_before_id_page_is_chronological(session):
    ch = _channel(session)
    conv = _conv_with_messages(session, ch, 5, texts=['a', 'b', 'c', 'd', 'e'])
    first_id = Message.query.filter_by(text='d').one().id
    msgs, has_more = inbox_service.get_thread(conv, before_id=first_id, limit=2)
    assert [m.text for m in msgs] == ['b', 'c']


# ── CRM client linking ─────────────────────────────────────────────────────

def test_ingest_auto_links_client_by_instagram_handle(session):
    from app.models import Client
    client = Client(instagram='ann')
    session.add(client)
    session.commit()

    ch = MessagingChannel(name='IG', channel_type='instagram', webhook_secret='x')
    session.add(ch)
    session.commit()

    inbox_service.ingest_event(ch, _msg_event())  # _msg_event contact username='ann'
    conv = Conversation.query.one()
    assert conv.client_id == client.id


def test_ingest_does_not_link_on_no_match(session):
    ch = MessagingChannel(name='IG', channel_type='instagram', webhook_secret='x')
    session.add(ch)
    session.commit()
    inbox_service.ingest_event(ch, _msg_event())  # no Client with instagram='ann' exists
    conv = Conversation.query.one()
    assert conv.client_id is None


def test_link_client_route_and_unlink(app, session):
    from app.models import Client
    client = Client(name='Тестовий Клієнт')  # no instagram/telegram/phone — display_name falls back to name
    session.add(client)
    ch = _channel(session)
    conv = Conversation(channel_id=ch.id, external_chat_id='c1')
    session.add(conv)
    session.commit()

    c = _logged_in_client(app, session)
    resp = c.post(f'/inbox/conversations/{conv.id}/link-client',
                  json={'client_id': client.id})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert body['panel']['linked'] is True
    assert body['panel']['client']['name'] == 'Тестовий Клієнт'

    resp2 = c.post(f'/inbox/conversations/{conv.id}/unlink-client')
    assert resp2.status_code == 200
    assert Conversation.query.get(conv.id).client_id is None


def test_link_client_route_rejects_unknown_client(app, session):
    ch = _channel(session)
    conv = Conversation(channel_id=ch.id, external_chat_id='c2')
    session.add(conv)
    session.commit()

    c = _logged_in_client(app, session)
    resp = c.post(f'/inbox/conversations/{conv.id}/link-client', json={'client_id': 999999})
    assert resp.status_code == 400
    assert resp.get_json()['ok'] is False


def test_client_panel_route_unlinked(app, session):
    ch = _channel(session)
    conv = Conversation(channel_id=ch.id, external_chat_id='c3')
    session.add(conv)
    session.commit()

    c = _logged_in_client(app, session)
    resp = c.get(f'/inbox/conversations/{conv.id}/client-panel')
    assert resp.status_code == 200
    assert resp.get_json() == {'linked': False, 'client': None, 'deliveries': []}


def test_clients_search_route(app, session):
    from app.models import Client
    session.add(Client(instagram='searchable_from_inbox'))
    session.commit()

    c = _logged_in_client(app, session)
    resp = c.get('/inbox/clients/search?q=searchable_from_inbox')
    assert resp.status_code == 200
    names = [x['instagram'] for x in resp.get_json()['clients']]
    assert 'searchable_from_inbox' in names


# ── contact enrichment / deferred auto-link ───────────────────────────────

def _bare_event(chat='777', mid='1', text='hi'):
    """An event with no contact info — what telegram_personal used to send."""
    return InboundEvent(kind='message', external_chat_id=chat, external_message_id=mid,
                        text=text, contact={}, media=[])


def test_contact_arriving_later_fills_name_and_links_client(session):
    from app.models.client import Client

    client = Client(telegram='@oksana_tg')
    session.add(client)
    ch = _channel(session, channel_type='telegram_personal')
    session.commit()

    inbox_service.ingest_event(ch, _bare_event(mid='1'))
    conv = Conversation.query.one()
    assert conv.display_name == '#777'
    assert conv.client_id is None

    # the worker now resolves the sender — the next message carries the contact
    inbox_service.ingest_event(ch, InboundEvent(
        kind='message', external_chat_id='777', external_message_id='2', text='hi again',
        contact={'name': 'Оксана', 'username': 'oksana_tg'}, media=[]))

    session.refresh(conv)
    assert conv.contact_name == 'Оксана'
    assert conv.contact_username == 'oksana_tg'
    assert conv.display_name == 'Оксана'
    assert conv.client_id == client.id


def test_manual_link_is_not_overwritten_by_auto_link(session):
    from app.models.client import Client

    auto = Client(telegram='@oksana_tg')
    manual = Client(telegram='@somebody')
    session.add_all([auto, manual])
    ch = _channel(session, channel_type='telegram_personal')
    session.commit()

    inbox_service.ingest_event(ch, _bare_event(mid='1'))
    conv = Conversation.query.one()
    inbox_service.link_client(conv, manual.id)

    inbox_service.ingest_event(ch, InboundEvent(
        kind='message', external_chat_id='777', external_message_id='2', text='x',
        contact={'username': 'oksana_tg'}, media=[]))

    session.refresh(conv)
    assert conv.client_id == manual.id


# ── outgoing messages, albums, timestamps ─────────────────────────────────

def _tg_media(mid, group=None):
    return {'type': 'photo', 'tg_chat_id': 777, 'tg_message_id': mid,
            'tg_access_hash': 5, 'tg_group_id': group, 'mime': 'image/jpeg', 'filename': None}


def test_outgoing_message_is_stored_as_out_and_clears_unread(session):
    ch = _channel(session, channel_type='telegram_personal')
    inbox_service.ingest_event(ch, _msg_event(chat='777', mid='1', text='питання'))
    conv = Conversation.query.one()
    assert conv.unread_count == 1

    # the owner answers from their phone — Telegram echoes it back to the worker
    msg = inbox_service.ingest_event(ch, InboundEvent(
        kind='message', external_chat_id='777', external_message_id='2',
        text='відповідь', contact={}, media=[], outgoing=True))

    assert msg.direction == 'out'
    assert msg.status == 'sent'
    session.refresh(conv)
    assert conv.unread_count == 0
    assert conv.last_message_direction == 'out'
    assert conv.last_message_preview == 'відповідь'


def test_reply_sent_from_the_crm_is_not_duplicated_by_its_echo(session):
    ch = _channel(session, channel_type='telegram_personal')
    inbox_service.ingest_event(ch, _msg_event(chat='777', mid='1'))
    conv = Conversation.query.one()

    echoed = InboundEvent(kind='message', external_chat_id='777', external_message_id='9',
                          text='з CRM', contact={}, media=[], outgoing=True)
    inbox_service.ingest_event(ch, echoed)
    inbox_service.ingest_event(ch, echoed)

    assert conv.messages.filter_by(external_message_id='9').count() == 1


def test_album_parts_merge_into_one_message(session):
    ch = _channel(session, channel_type='telegram_personal')

    first = inbox_service.ingest_event(ch, InboundEvent(
        kind='message', external_chat_id='777', external_message_id='10', text=None,
        contact={}, media=[_tg_media(10, group='abc')], group_id='abc'))
    second = inbox_service.ingest_event(ch, InboundEvent(
        kind='message', external_chat_id='777', external_message_id='11',
        text='дві світлини', contact={}, media=[_tg_media(11, group='abc')], group_id='abc'))

    conv = Conversation.query.one()
    assert conv.messages.count() == 1
    assert second.id == first.id
    assert [m['tg_message_id'] for m in second.media] == [10, 11]
    # the caption can sit on any part of the album
    assert second.text == 'дві світлини'
    # one album is one unread message, not one per photo
    assert conv.unread_count == 1


def test_album_part_redelivered_after_a_reconnect_is_ignored(session):
    ch = _channel(session, channel_type='telegram_personal')
    part = InboundEvent(kind='message', external_chat_id='777', external_message_id='10',
                        text=None, contact={}, media=[_tg_media(10, group='abc')], group_id='abc')
    second = InboundEvent(kind='message', external_chat_id='777', external_message_id='11',
                          text=None, contact={}, media=[_tg_media(11, group='abc')], group_id='abc')

    inbox_service.ingest_event(ch, part)
    inbox_service.ingest_event(ch, second)
    assert inbox_service.ingest_event(ch, second) is None

    msg = Message.query.one()
    assert len(msg.media) == 2


def test_serialized_timestamps_carry_the_utc_offset(session):
    """Without it the browser reads the naive string as local time and shows
    every message three hours early in Kyiv."""
    ch = _channel(session, channel_type='telegram_personal')
    inbox_service.ingest_event(ch, _msg_event(chat='777', mid='1'))
    conv = Conversation.query.one()
    msg = Message.query.one()

    assert inbox_service.serialize_message(msg)['created_at'].endswith('+00:00')
    assert inbox_service.serialize_conversation(conv)['last_message_at'].endswith('+00:00')


# ── read marks and reactions ──────────────────────────────────────────────

def _read_event(chat='777', max_id=5, inbox=False):
    return InboundEvent(kind='read', external_chat_id=chat, read_max_id=max_id,
                        read_inbox=inbox)


def test_read_mark_promotes_only_our_sent_messages_up_to_max_id(session):
    ch = _channel(session, channel_type='telegram_personal')
    inbox_service.ingest_event(ch, _msg_event(chat='777', mid='1', text='питання'))
    for mid in ('4', '5', '9'):
        inbox_service.ingest_event(ch, InboundEvent(
            kind='message', external_chat_id='777', external_message_id=mid,
            text='відповідь ' + mid, contact={}, media=[], outgoing=True))

    inbox_service.ingest_event(ch, _read_event(max_id=5))

    by_id = {m.external_message_id: m.status for m in Message.query.all()}
    assert by_id['4'] == 'read'
    assert by_id['5'] == 'read'
    assert by_id['9'] == 'sent'        # sent after they read
    assert by_id['1'] == 'received'    # theirs, not ours


def test_read_inbox_clears_the_unread_badge(session):
    ch = _channel(session, channel_type='telegram_personal')
    inbox_service.ingest_event(ch, _msg_event(chat='777', mid='1'))
    conv = Conversation.query.one()
    assert conv.unread_count == 1

    inbox_service.ingest_event(ch, _read_event(inbox=True))

    session.refresh(conv)
    assert conv.unread_count == 0


def test_read_event_for_an_unknown_chat_creates_nothing(session):
    ch = _channel(session, channel_type='telegram_personal')
    assert inbox_service.ingest_event(ch, _read_event(chat='404')) is None
    assert Conversation.query.count() == 0


def test_reactions_are_stored_replaced_and_cleared(session):
    ch = _channel(session, channel_type='telegram_personal')
    inbox_service.ingest_event(ch, _msg_event(chat='777', mid='1'))
    msg = Message.query.one()

    def react(items):
        return inbox_service.ingest_event(ch, InboundEvent(
            kind='reactions', external_chat_id='777', external_message_id='1',
            reactions=items))

    react([{'emoji': '👍', 'count': 1, 'mine': False}])
    session.refresh(msg)
    assert msg.reactions == [{'emoji': '👍', 'count': 1, 'mine': False}]

    # Telegram always sends the whole set, so a change replaces it wholesale
    react([{'emoji': '❤️', 'count': 2, 'mine': True}])
    session.refresh(msg)
    assert msg.reactions[0]['emoji'] == '❤️'

    react([])  # every reaction removed
    session.refresh(msg)
    assert msg.reactions is None


def test_recent_message_states_feed_the_poll(session):
    ch = _channel(session, channel_type='telegram_personal')
    inbox_service.ingest_event(ch, _msg_event(chat='777', mid='1'))
    conv = Conversation.query.one()
    inbox_service.ingest_event(ch, InboundEvent(
        kind='reactions', external_chat_id='777', external_message_id='1',
        reactions=[{'emoji': '👍', 'count': 1, 'mine': False}]))

    state = inbox_service.recent_message_states(conv)[0]
    assert state['status'] == 'received'
    assert state['reactions'][0]['emoji'] == '👍'


def test_delete_channel_removes_conversations_messages_and_media(app, session, tmp_path):
    from app.services.messaging import channel_config_service as ccs
    app.config['INBOX_MEDIA_FOLDER'] = str(tmp_path)
    (tmp_path / 'photo.jpg').write_bytes(b'x')

    ch = _channel(session)
    other = _channel(session, external_id='BC2')
    first = inbox_service.ingest_event(ch, _msg_event(mid='1'))
    second = inbox_service.ingest_event(ch, _msg_event(mid='2', text='with photo'))
    second.reply_to_message_id = first.id
    second.media = [{'type': 'photo', 'path': 'photo.jpg'}]
    inbox_service.ingest_event(other, _msg_event(chat='777', mid='1'))
    session.commit()

    ccs.delete_channel(ch)

    assert MessagingChannel.query.get(ch.id) is None
    assert Conversation.query.filter_by(channel_id=ch.id).count() == 0
    assert not (tmp_path / 'photo.jpg').exists()
    # the other channel is untouched
    assert Conversation.query.filter_by(channel_id=other.id).count() == 1
    assert Message.query.count() == 1

