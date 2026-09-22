"""One-time history import for a `telegram_personal` channel.

Only possible because this channel is a real MTProto session (not a bot) —
Telegram's Bot API gives no access to history from before a bot/webhook was
connected, but a personal session already has the full chat history locally
on Telegram's servers, same as opening Telegram Desktop.

Run via `flask messaging-backfill-telegram-personal <channel_id> [--days N]`.
Safe to re-run: already-imported messages (matched by external_message_id
within the conversation) are skipped.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.messaging.adapter import InboundEvent
from app.services.messaging.inbox_service import _get_or_create_conversation, apply_contact
from app.services.messaging.telegram_personal import client_for, _media_dicts, contact_from_entity


def run(channel, days: int = 30) -> dict:
    return asyncio.run(_run_async(channel, days))


async def _run_async(channel, days: int) -> dict:
    client = client_for(channel)
    await client.connect()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        dialogs_done = 0
        messages_imported = 0

        async for dialog in client.iter_dialogs():
            if not dialog.is_user:
                continue

            contact = contact_from_entity(dialog.entity)
            contact['name'] = contact.get('name') or dialog.name or None

            if getattr(dialog.entity, 'bot', False):
                # A bot's history is noise, so no conversation is created for it
                # here — but if the live worker already made one, it deserves a
                # name instead of a bare chat id.
                conv = Conversation.query.filter_by(
                    channel_id=channel.id, external_chat_id=str(dialog.id)).first()
                if conv:
                    apply_contact(conv, contact)
                    db.session.commit()
                continue

            fake_event = InboundEvent(
                kind='message',
                external_chat_id=str(dialog.id),
                contact=contact,
            )
            conv = _get_or_create_conversation(channel, fake_event)
            # Also repairs conversations created before the live worker passed
            # contact info through — they exist with a bare chat id and no client.
            apply_contact(conv, contact)
            db.session.commit()

            imported_this_dialog = []
            async for message in client.iter_messages(dialog.entity):
                if message.date < cutoff:
                    break
                if not message.message and not message.photo and not message.document:
                    continue  # service messages etc. — nothing worth showing
                external_id = str(message.id)
                exists = Message.query.filter_by(
                    conversation_id=conv.id, external_message_id=external_id).first()
                if exists:
                    continue
                imported_this_dialog.append(message)

            for message in reversed(imported_this_dialog):  # oldest first
                naive_date = message.date.replace(tzinfo=None)
                msg = Message(
                    conversation_id=conv.id,
                    direction='out' if message.out else 'in',
                    external_message_id=str(message.id),
                    text=message.message or None,
                    media=_media_dicts(message),
                    status='sent' if message.out else 'received',
                    tg_date=naive_date,
                    created_at=naive_date,
                )
                db.session.add(msg)
                messages_imported += 1
                if not conv.last_message_at or naive_date > conv.last_message_at:
                    conv.last_message_at = naive_date
                    conv.last_message_preview = (message.message or '')[:200] or (
                        '📷 Фото' if message.photo else '📎 Файл' if message.document else '')
                    conv.last_message_direction = 'out' if message.out else 'in'

            if imported_this_dialog:
                db.session.commit()
                dialogs_done += 1

        return {'dialogs': dialogs_done, 'messages': messages_imported}
    finally:
        await client.disconnect()
