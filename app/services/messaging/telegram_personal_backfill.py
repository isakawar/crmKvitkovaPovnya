"""One-time history import for a `telegram_personal` channel.

Only possible because this channel is a real MTProto session (not a bot) —
Telegram's Bot API gives no access to history from before a bot/webhook was
connected, but a personal session already has the full chat history locally
on Telegram's servers, same as opening Telegram Desktop.

Two entry points:
- `run()` / the `flask messaging-backfill-telegram-personal <channel_id>
  [--days N]` CLI command — whole-account, opens its own MTProto connection.
  Running it while `telegram-personal-bot` is already live-listening on the
  same session can silently stop that listener from receiving new messages;
  restart the worker after using this.
- `backfill_conversation()` — single conversation, takes an already-connected
  client (the live worker's own) so it never opens a second connection. This
  is what the CRM's "pull older history" button in /inbox uses, via a Redis
  command the worker picks up itself (see scripts/run_telegram_personal_worker.py
  `_listen_for_backfill`) — safe to call anytime, no restart needed.

Both are safe to re-run: already-imported messages (matched by
external_message_id within the conversation) are skipped.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.messaging.adapter import InboundEvent
from app.services.messaging.inbox_service import (
    _album_message, _get_or_create_conversation, _merge_into_album, apply_contact,
)
from app.services.messaging.telegram_personal import (
    _media_dicts, client_for, contact_from_entity, reactions_from_update,
)


def run(channel, days: int = 30) -> dict:
    return asyncio.run(_run_async(channel, days))


async def _backfill_dialog(client, dialog_entity, conv, days: int) -> int:
    """Import one dialog's history into `conv` using an already-connected
    client. Shared by the whole-account CLI backfill and the live worker's
    single-conversation backfill — the latter reuses its own already-connected
    client instead of opening a second one (see the module docstring's
    session-conflict note for why that matters)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    imported_this_dialog = []
    async for message in client.iter_messages(dialog_entity):
        if message.date < cutoff:
            break
        if not message.message and not message.photo and not message.document:
            continue  # service messages etc. — nothing worth showing
        exists = Message.query.filter_by(
            conversation_id=conv.id, external_message_id=str(message.id)).first()
        if exists:
            continue
        imported_this_dialog.append(message)

    messages_imported = 0
    for message in reversed(imported_this_dialog):  # oldest first
        naive_date = message.date.replace(tzinfo=None)
        media = _media_dicts(message, dialog_entity)
        group_id = str(message.grouped_id) if message.grouped_id else None
        event = InboundEvent(
            kind='message',
            external_chat_id=conv.external_chat_id,
            external_message_id=str(message.id),
            text=message.message or None,
            media=media,
            date=naive_date,
            outgoing=bool(message.out),
            group_id=group_id,
        )

        # Album parts are folded into one message, exactly as the live
        # worker does — same two helpers, so both paths agree.
        album = _album_message(conv, event) if group_id else None
        if album is not None:
            if _merge_into_album(album, event, media) is None:
                continue  # already imported by an earlier run
            messages_imported += 1
            continue

        msg = Message(
            conversation_id=conv.id,
            direction='out' if message.out else 'in',
            external_message_id=str(message.id),
            text=message.message or None,
            media=media,
            # Reactions ride along with the history: live updates that
            # landed while the worker was down are never replayed, so
            # this run is the only way to get them.
            reactions=reactions_from_update(message.reactions) or None,
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
    return messages_imported


async def backfill_conversation(client, conv, days: int) -> int:
    """Backfill one already-existing conversation using the live worker's
    already-connected client — never opens a second MTProto connection."""
    entity = await client.get_entity(int(conv.external_chat_id))
    contact = contact_from_entity(entity)
    contact['name'] = contact.get('name') or conv.contact_name or None
    apply_contact(conv, contact)
    db.session.commit()
    return await _backfill_dialog(client, entity, conv, days)


async def _run_async(channel, days: int) -> dict:
    client = client_for(channel)
    await client.connect()
    try:
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

            imported = await _backfill_dialog(client, dialog.entity, conv, days)
            if imported:
                messages_imported += imported
                dialogs_done += 1

        return {'dialogs': dialogs_done, 'messages': messages_imported}
    finally:
        await client.disconnect()
