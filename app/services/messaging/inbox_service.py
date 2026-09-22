"""Channel-agnostic inbox domain logic.

No Flask request/response here. Media files are downloaded lazily so the
inbound webhook can always return 200 fast (Telegram retries on timeout).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy.orm.attributes import flag_modified

from app.extensions import db
from app.models.client import Client
from app.models.conversation import Conversation
from app.models.delivery import Delivery
from app.models.message import Message
from app.models.messaging_channel import MessagingChannel
from app.models.messaging_channel_access import MessagingChannelAccess
from app.models.subscription import Subscription
from app.services import client_service
from app.services.messaging import events
from app.services.messaging.adapter import get_adapter

log = logging.getLogger(__name__)

_ADMIN_TYPES = ('admin',)
_MANAGER_TYPES = ('admin', 'manager')

# Bounds concurrent background media downloads (webhook bursts, backfills) so
# a flood of inbound attachments can't spawn unbounded OS threads.
_MEDIA_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix='inbox-media')


# --- access -------------------------------------------------------------
def user_is_manager(user) -> bool:
    return (getattr(user, 'user_type', None) in _MANAGER_TYPES
            or (hasattr(user, 'has_role') and user.has_role('admin')))


def accessible_channel_ids(user) -> list[int]:
    if getattr(user, 'user_type', None) in _ADMIN_TYPES or (
            hasattr(user, 'has_role') and user.has_role('admin')):
        return [c.id for c in MessagingChannel.query.all()]
    rows = MessagingChannelAccess.query.filter_by(user_id=user.id).all()
    return [r.channel_id for r in rows]


def user_can_access(user, channel_or_conv) -> bool:
    channel_id = getattr(channel_or_conv, 'channel_id', None) or getattr(channel_or_conv, 'id', None)
    return user_is_manager(user) and channel_id in set(accessible_channel_ids(user))


# --- inbound -----------------------------------------------------------
def ingest_event(channel: MessagingChannel, event) -> Message | None:
    """Persist one normalized InboundEvent. Never raises — logs and returns None."""
    try:
        if event.kind == 'connection':
            channel.external_id = event.connection_id if event.connection_enabled else None
            channel.is_active = event.connection_enabled
            db.session.commit()
            return None

        # Instagram: learn our own account id from the first webhook
        account_id = event.contact.get('_account_id') if event.contact else None
        if account_id and not channel.external_id:
            channel.external_id = account_id

        conv = _get_or_create_conversation(channel, event)

        if event.kind == 'deleted':
            (Message.query
             .filter(Message.conversation_id == conv.id,
                     Message.external_message_id.in_(event.deleted_message_ids))
             .update({'status': 'deleted'}, synchronize_session=False))
            db.session.commit()
            events.publish('message', channel.id, conv.id)
            return None

        if event.kind == 'edited':
            msg = Message.query.filter_by(
                conversation_id=conv.id, external_message_id=event.external_message_id).first()
            if msg:
                msg.text = event.text
                db.session.commit()
                events.publish('message', channel.id, conv.id)
            return msg

        # kind == 'message'
        # Providers can redeliver an update we've already processed (Telegram
        # Business retries on a slow webhook response; a personal-number
        # MTProto session can get the same recent update replayed after a
        # reconnect — happens on every worker restart). Without this guard
        # each redelivery silently inserts a duplicate row.
        if event.external_message_id and Message.query.filter_by(
                conversation_id=conv.id, external_message_id=event.external_message_id).first():
            return None

        # keep whatever fields the adapter put in each media dict
        # (telegram/instagram use tg_file_id, telegram_personal uses
        # tg_chat_id/tg_message_id instead — download_media needs its own shape).
        media = [dict(m, path=None) for m in event.media]

        # An album arrives as several separate messages sharing one group id —
        # merge them into the message that opened the album so the thread shows
        # one bubble with several photos, the way Telegram itself does.
        album = _album_message(conv, event) if event.group_id else None
        if album is not None:
            msg = _merge_into_album(album, event, media)
            if msg is None:
                return None
        else:
            msg = Message(
                conversation_id=conv.id,
                direction='out' if event.outgoing else 'in',
                external_message_id=event.external_message_id,
                text=event.text,
                media=media,
                status='sent' if event.outgoing else 'received',
                tg_date=event.date,
            )
            db.session.add(msg)

        apply_contact(conv, event.contact)

        conv.last_message_at = event.date or datetime.utcnow()
        conv.last_message_preview = _preview(msg.text, msg.media)
        if event.outgoing:
            # The owner answering from their phone means they've seen the chat.
            conv.last_message_direction = 'out'
            conv.unread_count = 0
        else:
            conv.last_message_direction = 'in'
            if album is None:
                conv.unread_count = (conv.unread_count or 0) + 1
        db.session.commit()
        events.publish('message', channel.id, conv.id)
        return msg
    except Exception:  # noqa: BLE001
        db.session.rollback()
        log.exception('ingest_event failed for channel %s', getattr(channel, 'id', '?'))
        return None


_ALBUM_LOOKBACK = 10


def _album_message(conv: Conversation, event) -> Message | None:
    """The already-stored message of this event's album, if there is one.

    The album id isn't a column — it rides along in each media dict, so this
    only scans the last few messages of the conversation (album parts always
    arrive back to back).
    """
    recent = (conv.messages.order_by(None).order_by(Message.id.desc())
              .limit(_ALBUM_LOOKBACK).all())
    for msg in recent:
        for item in msg.media or []:
            if item.get('tg_group_id') == event.group_id:
                return msg
    return None


def _merge_into_album(msg: Message, event, media: list[dict]) -> Message | None:
    """Append this album part's media to the album's message. None if already there.

    Redelivery is caught here rather than by the external_message_id guard: the
    album keeps the id of the message that opened it, so the later parts have
    no row of their own to match against.
    """
    known = {item.get('tg_message_id') for item in msg.media or []}
    fresh = [m for m in media if m.get('tg_message_id') not in known]
    if not fresh:
        return None
    msg.media = list(msg.media or []) + fresh
    flag_modified(msg, 'media')
    # The caption can sit on any part of the album, not only the first.
    if event.text and not msg.text:
        msg.text = event.text
    return msg


def apply_contact(conv: Conversation, contact: dict | None) -> None:
    """Fill in whatever contact fields the event carries, then retry auto-link.

    Contact info doesn't always arrive with the first message (a
    telegram_personal conversation created before the worker learned to
    resolve senders has none at all), so both the fields and the CRM-client
    match are re-attempted on every event rather than only at creation.
    """
    if not contact:
        return
    conv.contact_name = contact.get('name') or conv.contact_name
    conv.contact_username = contact.get('username') or conv.contact_username
    conv.contact_phone = contact.get('phone') or conv.contact_phone
    _try_auto_link(conv)


def _try_auto_link(conv: Conversation, channel_type: str | None = None) -> None:
    """Link an unlinked conversation to a CRM client, if exactly one matches.

    `channel_type` is passed explicitly where the conversation may not be in
    the session yet — touching `conv.channel` there makes SQLAlchemy's
    autoflush complain about a half-attached backref.
    """
    if conv.client_id or not (conv.contact_username or conv.contact_phone):
        return
    try:
        client = client_service.find_client_for_contact(
            channel_type or conv.channel.channel_type,
            username=conv.contact_username,
            phone=conv.contact_phone,
        )
        if client:
            conv.client_id = client.id
    except Exception:  # noqa: BLE001
        log.exception('find_client_for_contact failed')


def _get_or_create_conversation(channel: MessagingChannel, event) -> Conversation:
    conv = Conversation.query.filter_by(
        channel_id=channel.id, external_chat_id=event.external_chat_id).first()
    if conv is None:
        contact = dict(event.contact or {})
        if not contact.get('name') and not contact.get('username'):
            adapter = get_adapter(channel)
            if hasattr(adapter, 'enrich_contact'):
                try:
                    contact.update({k: v for k, v in
                                    adapter.enrich_contact(channel, event.external_chat_id).items()
                                    if v})
                except Exception:  # noqa: BLE001
                    log.exception('enrich_contact failed')
        conv = Conversation(
            channel_id=channel.id,
            external_chat_id=event.external_chat_id,
            contact_name=contact.get('name'),
            contact_username=contact.get('username'),
            contact_phone=contact.get('phone'),
        )
        db.session.add(conv)
        db.session.flush()
        _try_auto_link(conv, channel.channel_type)
    return conv


def _preview(text: str | None, media: list[dict]) -> str:
    if text:
        return text[:200]
    if media:
        kinds = {m.get('type') for m in media}
        label = {'photo': '📷 Фото', 'voice': '🎤 Голосове',
                 'video': '🎬 Відео', 'document': '📎 Файл'}
        return ', '.join(label.get(k, '📎 Вкладення') for k in kinds)
    return ''


# --- lazy media ------------------------------------------------------
def ensure_media_downloaded(message: Message, idx: int) -> str | None:
    """Download media[idx] to disk if not present. Returns stored filename or None."""
    media = [dict(m) for m in (message.media or [])]  # fresh dicts — see note below
    if idx < 0 or idx >= len(media):
        return None
    item = media[idx]
    if item.get('path'):
        return item['path']
    if item.get('expired'):
        return None  # purged by media_cleanup.purge_old_media — gone for good
    adapter = get_adapter(message.conversation.channel)
    try:
        stored, mime = adapter.download_media(message.conversation.channel, item)
    except Exception:  # noqa: BLE001
        log.exception('media download failed for message %s idx %s', message.id, idx)
        return None
    item['path'] = stored
    item['mime'] = item.get('mime') or mime
    media[idx] = item
    message.media = media
    # `media` is a plain JSON column — SQLAlchemy only detects the change if the
    # new value differs from the old one by more than in-place-mutated shared
    # dicts (copying with dict(m) above avoids that), and flag_modified makes
    # the intent explicit regardless.
    flag_modified(message, 'media')
    db.session.add(message)
    db.session.commit()
    return stored


def prefetch_message_media(app, message_id: int) -> None:
    """Best-effort background download of every attachment on a message."""
    def _run():
        with app.app_context():
            msg = db.session.get(Message, message_id)
            if not msg:
                return
            for i in range(len(msg.media or [])):
                ensure_media_downloaded(msg, i)
    _MEDIA_POOL.submit(_run)


# --- outbound -------------------------------------------------------
def send_reply(conversation: Conversation, user, text: str | None,
               file_path: str | None = None, file_caption: str | None = None) -> Message:
    adapter = get_adapter(conversation.channel)
    media = []
    if file_path:
        result = adapter.send_media(conversation.channel, conversation.external_chat_id,
                                    file_path, caption=file_caption or text)
        import os
        media = [{'type': 'photo', 'path': os.path.basename(file_path),
                  'mime': 'image/jpeg', 'filename': None, 'tg_file_id': None}]
    else:
        result = adapter.send_text(conversation.channel, conversation.external_chat_id, text or '')

    msg = Message(
        conversation_id=conversation.id,
        direction='out',
        sender_user_id=getattr(user, 'id', None),
        external_message_id=result.external_message_id,
        text=text,
        media=media,
        status='sent' if result.ok else 'failed',
        error=result.error,
        tg_date=datetime.utcnow() if result.ok else None,
    )
    db.session.add(msg)
    if result.ok:
        conversation.last_message_at = datetime.utcnow()
        conversation.last_message_preview = _preview(text, media)
        conversation.last_message_direction = 'out'
        conversation.unread_count = 0
    db.session.commit()
    events.publish('message', conversation.channel_id, conversation.id)
    return msg


# --- reads -----------------------------------------------------------
def list_conversations(user, unread_only: bool = False, channel_ids: list[int] | None = None):
    if channel_ids is None:
        channel_ids = accessible_channel_ids(user)
    if not channel_ids:
        return []
    q = (Conversation.query
         .options(db.joinedload(Conversation.channel))
         .filter(Conversation.channel_id.in_(channel_ids)))
    if unread_only:
        q = q.filter(Conversation.unread_count > 0)
    return q.order_by(Conversation.last_message_at.desc().nullslast(),
                      Conversation.id.desc()).all()


def get_thread(conversation: Conversation, after_id: int | None = None,
               before_id: int | None = None, limit: int = 50):
    """Return (messages, has_more).

    - after_id: everything newer (polling for new messages) — unbounded,
      there's never many of these between two 5s polls.
    - before_id: a page of older messages (scrolling up), newest-first then
      reversed to chronological order.
    - neither: the initial page — the most recent `limit` messages.
    """
    if after_id:
        msgs = (conversation.messages.filter(Message.id > after_id)
                .order_by(Message.id).all())
        return msgs, False

    q = conversation.messages
    if before_id:
        q = q.filter(Message.id < before_id)
    # `conversation.messages` is a dynamic relationship with its own baked-in
    # `ORDER BY id ASC` (see Conversation.messages) — appending `.desc()`
    # without resetting first produces `ORDER BY id ASC, id DESC`, and since
    # `id` is unique the first clause wins outright, silently ignoring the
    # `.desc()` and returning the OLDEST `limit` rows instead of the newest.
    msgs = q.order_by(None).order_by(Message.id.desc()).limit(limit).all()
    msgs.reverse()
    return msgs, len(msgs) == limit


def mark_read(conversation: Conversation) -> None:
    if conversation.unread_count:
        conversation.unread_count = 0
        db.session.commit()


def total_unread(user, channel_ids: list[int] | None = None) -> int:
    if channel_ids is None:
        channel_ids = accessible_channel_ids(user)
    if not channel_ids:
        return 0
    return int(db.session.query(db.func.coalesce(db.func.sum(Conversation.unread_count), 0))
               .filter(Conversation.channel_id.in_(channel_ids))
               .scalar() or 0)


def start_conversation(channel: MessagingChannel, query: str) -> Conversation:
    """Resolve a contact (phone/username) and get-or-create its conversation.

    Only channel types whose adapter implements `resolve_contact` (currently
    telegram_personal — a real account can message anyone, unlike a webhook bot).
    """
    adapter = get_adapter(channel)
    if not hasattr(adapter, 'resolve_contact'):
        raise RuntimeError('Цей канал не підтримує ручний початок діалогу')
    contact = adapter.resolve_contact(channel, query)

    conv = Conversation.query.filter_by(
        channel_id=channel.id, external_chat_id=contact['external_chat_id']).first()
    if conv is None:
        conv = Conversation(
            channel_id=channel.id,
            external_chat_id=contact['external_chat_id'],
            contact_name=contact.get('name'),
            contact_username=contact.get('username'),
            contact_phone=contact.get('phone'),
        )
        db.session.add(conv)
        db.session.commit()
    return conv


# --- serialization for JSON endpoints ------------------------------
def serialize_conversation(conv: Conversation) -> dict:
    return {
        'id': conv.id,
        'channel_id': conv.channel_id,
        'channel_type': conv.channel.channel_type if conv.channel else None,
        'name': conv.display_name,
        'username': conv.contact_username,
        'preview': conv.last_message_preview or '',
        'direction': conv.last_message_direction,
        'unread': conv.unread_count or 0,
        'status': conv.status,
        'assigned_user_id': conv.assigned_user_id,
        'client_id': conv.client_id,
        'last_message_at': _iso_utc(conv.last_message_at),
    }


# --- CRM client linking --------------------------------------------
def link_client(conversation: Conversation, client_id: int) -> Client | None:
    client = db.session.get(Client, client_id)
    if not client:
        return None
    conversation.client_id = client.id
    db.session.commit()
    return client


def unlink_client(conversation: Conversation) -> None:
    conversation.client_id = None
    db.session.commit()


def get_client_panel(conversation: Conversation) -> dict:
    """Client summary + recent deliveries for the inbox's side panel.

    Deliveries are fetched directly by `Delivery.client_id` — cheap, and
    independent of which of the client's orders/subscriptions they belong to.
    """
    client = conversation.client
    if not client:
        return {'linked': False, 'client': None, 'deliveries': []}

    deliveries = (Delivery.query.filter_by(client_id=client.id)
                 .order_by(Delivery.delivery_date.desc()).limit(8).all())
    subscription = (Subscription.query.filter_by(client_id=client.id, status='active')
                    .order_by(Subscription.id.desc()).first())
    return {
        'linked': True,
        'client': {
            'id': client.id,
            'name': client.display_name,
            'phone': client.phone or '',
            'instagram': client.instagram or '',
            'telegram': client.telegram or '',
            'credits': float(client.credits or 0),
            'personal_discount': client.personal_discount or '',
        },
        'subscription': {
            'type': subscription.type,
            'delivery_day': subscription.delivery_day,
            'size': subscription.size,
            'is_wedding': subscription.is_wedding,
        } if subscription else None,
        'deliveries': [
            {
                'id': d.id,
                'date': d.delivery_date.isoformat() if d.delivery_date else None,
                'status': d.status,
                'address': ', '.join(p for p in [d.street, d.building_number] if p) or ('Самовивіз' if d.is_pickup else ''),
                'size': d.size or '',
            }
            for d in deliveries
        ],
    }


def _iso_utc(dt: datetime | None) -> str | None:
    """ISO string with an explicit +00:00 offset.

    Every datetime here is naive UTC; without the offset the browser's
    `new Date()` reads the string as local time, which showed every message
    three hours early in Kyiv.
    """
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat()


def serialize_message(msg: Message, channel_type: str | None = None) -> dict:
    return {
        'id': msg.id,
        'direction': msg.direction,
        'text': msg.text,
        'status': msg.status,
        'error': msg.error,
        'sender_user_id': msg.sender_user_id,
        'channel_type': channel_type or msg.conversation.channel.channel_type,
        'media': [
            {'idx': i, 'type': m.get('type'),
             'downloaded': bool(m.get('path')), 'expired': bool(m.get('expired'))}
            for i, m in enumerate(msg.media or [])
        ],
        'created_at': _iso_utc(msg.tg_date or msg.created_at),
    }
