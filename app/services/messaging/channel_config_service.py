"""CRUD for messaging channels + manager access, and webhook registration."""
from __future__ import annotations

import logging
import os
import secrets

from flask import current_app

from app.extensions import db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.messaging_channel import MessagingChannel
from app.models.messaging_channel_access import MessagingChannelAccess
from app.services.messaging.adapter import get_adapter

log = logging.getLogger(__name__)


def list_channels():
    return MessagingChannel.query.order_by(MessagingChannel.created_at).all()


def create_channel(name: str, channel_type: str = 'telegram') -> MessagingChannel:
    channel = MessagingChannel(
        name=name.strip(),
        channel_type=channel_type,
        webhook_secret=secrets.token_urlsafe(24),
    )
    db.session.add(channel)
    db.session.commit()
    return channel


def create_whatsapp_channel_from_signup(*, waba_id: str, phone_number_id: str,
                                         display_phone_number: str, access_token_encrypted: str) -> MessagingChannel:
    """WhatsApp channel connected via Embedded Signup (facebook_oauth.py) —
    the popup already resolved everything, no manual token entry."""
    channel = MessagingChannel(
        name=f'WhatsApp ({display_phone_number})' if display_phone_number else f'WhatsApp ({phone_number_id})',
        channel_type='whatsapp',
        external_id=phone_number_id,
        wa_waba_id=waba_id,
        wa_access_token_encrypted=access_token_encrypted,
        webhook_secret=secrets.token_urlsafe(24),
    )
    db.session.add(channel)
    db.session.commit()
    return channel


def create_instagram_channel_from_page(*, page_id: str, page_name: str, ig_id: str,
                                        ig_username: str, page_access_token_encrypted: str) -> MessagingChannel:
    """Instagram channel connected via Facebook Login (facebook_oauth.py) —
    the page picker already resolved everything, no manual token entry."""
    channel = MessagingChannel(
        name=f'Instagram (@{ig_username})' if ig_username else f'Instagram ({page_name})',
        channel_type='instagram',
        external_id=ig_id,
        fb_page_id=page_id,
        fb_page_access_token_encrypted=page_access_token_encrypted,
        webhook_secret=secrets.token_urlsafe(24),
    )
    db.session.add(channel)
    db.session.commit()
    return channel


def update_channel(channel: MessagingChannel, *, name=None, is_active=None) -> None:
    if name is not None:
        channel.name = name.strip()
    if is_active is not None:
        channel.is_active = bool(is_active)
    db.session.commit()


def delete_channel(channel: MessagingChannel) -> None:
    """Delete the channel with all its conversations, messages and downloaded
    media files. Rows are removed explicitly (not left to ON DELETE CASCADE) so
    the result doesn't depend on the DB enforcing FKs (SQLite in tests)."""
    conv_ids = db.session.query(Conversation.id).filter(Conversation.channel_id == channel.id)
    messages = Message.query.filter(Message.conversation_id.in_(conv_ids))

    folder = current_app.config.get('INBOX_MEDIA_FOLDER')
    if folder:
        for msg in messages.filter(Message.media.isnot(None)).all():
            for item in msg.media or []:
                path = item.get('path')
                if not path:
                    continue
                try:
                    os.remove(os.path.join(folder, path))
                except FileNotFoundError:
                    pass
                except OSError:
                    log.exception('failed to delete media file %s (message %s)', path, msg.id)

    # reply_to_message_id is a self-FK — clear it first so the bulk delete
    # doesn't trip over rows referencing each other.
    messages.update({Message.reply_to_message_id: None}, synchronize_session=False)
    messages.delete(synchronize_session=False)
    Conversation.query.filter(Conversation.channel_id == channel.id).delete(synchronize_session=False)
    db.session.delete(channel)
    db.session.commit()


def set_managers(channel: MessagingChannel, user_ids: list[int]) -> None:
    wanted = set(user_ids)
    current = {a.user_id: a for a in channel.access_entries}
    for uid in wanted - set(current):
        db.session.add(MessagingChannelAccess(channel_id=channel.id, user_id=uid))
    for uid in set(current) - wanted:
        db.session.delete(current[uid])
    db.session.commit()


def webhook_path(channel: MessagingChannel) -> str:
    return f'/api/messaging/{channel.channel_type}/{channel.id}/webhook'


def webhook_url(channel: MessagingChannel) -> str:
    base = (current_app.config.get('CRM_PUBLIC_URL') or '').rstrip('/')
    if not base:
        raise RuntimeError('CRM_PUBLIC_URL не налаштовано — Telegram потребує публічний HTTPS URL')
    return f'{base}{webhook_path(channel)}'


def register_webhook(channel: MessagingChannel) -> None:
    """Point the provider at our webhook route. Raises on provider error."""
    adapter = get_adapter(channel)
    adapter.register_webhook(channel, webhook_url(channel))
