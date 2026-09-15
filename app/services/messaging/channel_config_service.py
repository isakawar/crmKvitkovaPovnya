"""CRUD for messaging channels + manager access, and webhook registration."""
from __future__ import annotations

import secrets

from flask import current_app

from app.extensions import db
from app.models.messaging_channel import MessagingChannel
from app.models.messaging_channel_access import MessagingChannelAccess
from app.services.messaging.adapter import get_adapter


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
