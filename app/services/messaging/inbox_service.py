"""Channel-agnostic inbox domain logic.

No Flask request/response here. Media files are downloaded lazily so the
inbound webhook can always return 200 fast (Telegram retries on timeout).
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime

from sqlalchemy.orm.attributes import flag_modified

from app.extensions import db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.messaging_channel import MessagingChannel
from app.models.messaging_channel_access import MessagingChannelAccess
from app.services.messaging.adapter import get_adapter

log = logging.getLogger(__name__)

_ADMIN_TYPES = ('admin',)
_MANAGER_TYPES = ('admin', 'manager')


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
            return None

        if event.kind == 'edited':
            msg = Message.query.filter_by(
                conversation_id=conv.id, external_message_id=event.external_message_id).first()
            if msg:
                msg.text = event.text
                db.session.commit()
            return msg

        # kind == 'message' — keep whatever fields the adapter put in each media
        # dict (telegram/instagram use tg_file_id, telegram_personal uses
        # tg_chat_id/tg_message_id instead — download_media needs its own shape).
        media = [dict(m, path=None) for m in event.media]
        msg = Message(
            conversation_id=conv.id,
            direction='in',
            external_message_id=event.external_message_id,
            text=event.text,
            media=media,
            status='received',
            tg_date=event.date,
        )
        db.session.add(msg)

        if event.contact:
            conv.contact_name = event.contact.get('name') or conv.contact_name
            conv.contact_username = event.contact.get('username') or conv.contact_username
            conv.contact_phone = event.contact.get('phone') or conv.contact_phone

        conv.last_message_at = event.date or datetime.utcnow()
        conv.last_message_preview = _preview(event.text, media)
        conv.last_message_direction = 'in'
        conv.unread_count = (conv.unread_count or 0) + 1
        db.session.commit()
        return msg
    except Exception:  # noqa: BLE001
        db.session.rollback()
        log.exception('ingest_event failed for channel %s', getattr(channel, 'id', '?'))
        return None


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
    threading.Thread(target=_run, daemon=True).start()


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
    return msg


# --- reads -----------------------------------------------------------
def list_conversations(user, unread_only: bool = False):
    channel_ids = accessible_channel_ids(user)
    if not channel_ids:
        return []
    q = Conversation.query.filter(Conversation.channel_id.in_(channel_ids))
    if unread_only:
        q = q.filter(Conversation.unread_count > 0)
    return q.order_by(Conversation.last_message_at.desc().nullslast(),
                      Conversation.id.desc()).all()


def get_thread(conversation: Conversation, after_id: int | None = None):
    q = conversation.messages
    if after_id:
        q = q.filter(Message.id > after_id)
    return q.order_by(Message.id).all()


def mark_read(conversation: Conversation) -> None:
    if conversation.unread_count:
        conversation.unread_count = 0
        db.session.commit()


def total_unread(user) -> int:
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
        'last_message_at': conv.last_message_at.isoformat() if conv.last_message_at else None,
    }


def serialize_message(msg: Message) -> dict:
    return {
        'id': msg.id,
        'direction': msg.direction,
        'text': msg.text,
        'status': msg.status,
        'error': msg.error,
        'sender_user_id': msg.sender_user_id,
        'media': [
            {'idx': i, 'type': m.get('type'),
             'downloaded': bool(m.get('path')), 'expired': bool(m.get('expired'))}
            for i, m in enumerate(msg.media or [])
        ],
        'created_at': (msg.tg_date or msg.created_at).isoformat(),
    }
