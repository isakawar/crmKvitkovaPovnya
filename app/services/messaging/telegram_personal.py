"""Telegram "personal number" adapter (MTProto/Telethon) — send/download side.

WARNING: this sends/receives as a real personal Telegram account, not a bot.
See `telegram_personal_auth.py` for the login handshake and its risk note.

Unlike the webhook-shaped adapters, this channel has no HTTP webhook at all:
inbound messages are pushed straight into `inbox_service.ingest_event` by the
long-running worker process (`scripts/run_telegram_personal_worker.py`), which
holds one persistent Telethon client per channel. This adapter only covers
the request/response side (outbound send + on-demand media download), each
call opening a short-lived connection from the same (encrypted) session
string. `StringSession` — not the default file-based session — is what makes
it safe for the web process and the worker to both connect from the same
session concurrently.
"""
from __future__ import annotations

import asyncio
import os
import uuid

from flask import current_app
from telethon import TelegramClient
from telethon.sessions import StringSession

from app.services.messaging import session_crypto
from app.services.messaging.adapter import InboundEvent, SentResult

_EXT_BY_MIME = {
    'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
    'audio/ogg': '.ogg', 'video/mp4': '.mp4',
}


def _api_creds() -> tuple[int, str]:
    api_id = current_app.config.get('MESSAGING_TG_API_ID')
    api_hash = current_app.config.get('MESSAGING_TG_API_HASH')
    if not api_id or not api_hash:
        raise RuntimeError('MESSAGING_TG_API_ID/MESSAGING_TG_API_HASH не налаштовано')
    return int(api_id), api_hash


def client_for(channel) -> TelegramClient:
    """Build a (not-yet-connected) Telethon client from the channel's stored session.

    Shared with the worker process — both use the same StringSession-based
    construction so a channel's session behaves identically everywhere.
    """
    if not channel.session_encrypted:
        raise RuntimeError('Канал не підключено (немає сесії)')
    api_id, api_hash = _api_creds()
    session_str = session_crypto.decrypt(channel.session_encrypted)
    return TelegramClient(StringSession(session_str), api_id, api_hash)


def _media_dicts(message, peer=None) -> list[dict]:
    """Media entries shaped for download_media (tg_chat_id/tg_message_id, not
    tg_file_id like the bot adapters) — shared by the live worker and the
    history backfill script so both produce identically-downloadable media.

    `tg_access_hash` is what lets a download open a fresh session later: a
    newly connected client has an empty entity cache and cannot turn a bare
    user id into a peer on its own (see _download_media_async)."""
    common = {
        'tg_chat_id': message.chat_id,
        'tg_message_id': message.id,
        'tg_access_hash': getattr(peer, 'access_hash', None),
        'tg_group_id': str(message.grouped_id) if getattr(message, 'grouped_id', None) else None,
    }
    media = []
    if message.photo:
        media.append({**common, 'type': 'photo', 'mime': 'image/jpeg', 'filename': None})
    elif message.document:
        mime = message.document.mime_type or 'application/octet-stream'
        filename = None
        for attr in message.document.attributes:
            if getattr(attr, 'file_name', None):
                filename = attr.file_name
                break
        media.append({**common, 'type': 'document', 'mime': mime, 'filename': filename})
    return media


def contact_from_entity(entity) -> dict:
    """Telethon User entity -> the contact dict InboundEvent/Conversation expect.

    Without this the conversation has no name at all and shows as its raw chat
    id, and `client_service.find_client_for_contact` has no handle/phone to
    match a CRM client on.
    """
    if entity is None:
        return {}
    name = ' '.join(p for p in [getattr(entity, 'first_name', None),
                                getattr(entity, 'last_name', None)] if p) or None
    return {
        'name': name or getattr(entity, 'title', None),
        'username': getattr(entity, 'username', None),
        'phone': getattr(entity, 'phone', None),
    }


def build_inbound_event(message, peer=None) -> InboundEvent:
    """Normalize a Telethon `events.NewMessage.Event.message` into InboundEvent.

    `peer` is the resolved Telethon entity of the other party — in a 1:1 chat
    that is the contact in both directions. The worker awaits `event.get_chat()`
    and passes it in, since only it runs inside the live asyncio loop. Omitted
    (None) the conversation falls back to
    `TelegramPersonalAdapter.enrich_contact`, and a media download falls back to
    priming the entity cache.
    """
    return InboundEvent(
        kind='message',
        external_chat_id=str(message.chat_id),
        external_message_id=str(message.id),
        text=message.message or None,
        contact=contact_from_entity(peer),
        media=_media_dicts(message, peer),
        date=message.date.replace(tzinfo=None) if message.date else None,
        outgoing=bool(getattr(message, 'out', False)),
        group_id=str(message.grouped_id) if getattr(message, 'grouped_id', None) else None,
    )


def reactions_from_update(message_reactions) -> list[dict]:
    """MTProto MessageReactions -> [{emoji, count, mine}].

    Telegram always sends the whole current set, so an empty list genuinely
    means every reaction was removed. Paid custom-emoji reactions have no
    unicode form and are shown as a generic star.
    """
    items = []
    for result in getattr(message_reactions, 'results', None) or []:
        reaction = getattr(result, 'reaction', None)
        emoji = getattr(reaction, 'emoticon', None) or '\u2b50'
        items.append({
            'emoji': emoji,
            'count': int(getattr(result, 'count', 0) or 0),
            'mine': getattr(result, 'chosen_order', None) is not None,
        })
    return items


def build_reactions_event(update) -> InboundEvent:
    """UpdateMessageReactions -> InboundEvent.

    `get_peer_id` is what `message.chat_id` is built from too, so the id here
    matches the one the conversation was stored under.
    """
    from telethon import utils
    return InboundEvent(
        kind='reactions',
        external_chat_id=str(utils.get_peer_id(update.peer)),
        external_message_id=str(update.msg_id),
        reactions=reactions_from_update(update.reactions),
    )


def build_read_event(chat_id, max_id: int, inbox: bool) -> InboundEvent:
    return InboundEvent(
        kind='read',
        external_chat_id=str(chat_id),
        read_max_id=int(max_id) if max_id else None,
        read_inbox=bool(inbox),
    )


class TelegramPersonalAdapter:
    channel_type = 'telegram_personal'

    # --- inbound (unused — the worker calls inbox_service directly) --------
    def verify_webhook(self, request, channel) -> bool:
        raise NotImplementedError('telegram_personal has no webhook — the worker ingests events directly')

    def verify_subscription(self, args, channel) -> str | None:
        raise NotImplementedError('telegram_personal has no webhook — the worker ingests events directly')

    def parse_events(self, payload: dict) -> list[InboundEvent]:
        raise NotImplementedError('telegram_personal has no webhook — the worker ingests events directly')

    def download_media(self, channel, media_ref: dict) -> tuple[str, str]:
        return asyncio.run(self._download_media_async(channel, media_ref))

    async def _resolve_peer(self, client, media_ref: dict):
        """An input peer this freshly connected client can actually use.

        A new client's entity cache is empty, so a bare user id raises
        "Could not find the input entity for PeerUser(...)" and the download
        fails. The access hash stored with the media resolves it outright;
        media saved before that was stored falls back to pulling the dialog
        list once, which is what fills the cache.
        """
        chat_id = media_ref['tg_chat_id']
        access_hash = media_ref.get('tg_access_hash')
        if access_hash is not None:
            from telethon.tl.types import InputPeerUser
            return InputPeerUser(int(chat_id), int(access_hash))
        await client.get_dialogs()
        return int(chat_id)

    async def _download_media_async(self, channel, media_ref: dict) -> tuple[str, str]:
        client = client_for(channel)
        await client.connect()
        try:
            peer = await self._resolve_peer(client, media_ref)
            message = await client.get_messages(peer, ids=media_ref['tg_message_id'])
            if message is None:
                raise RuntimeError('Повідомлення з медіа більше не існує')

            max_bytes = current_app.config.get('INBOX_MEDIA_MAX_BYTES', 15 * 1024 * 1024)
            size = getattr(message.file, 'size', None)
            if size and size > max_bytes:
                raise RuntimeError(f'media too large: {size} bytes')

            mime = media_ref.get('mime') or 'application/octet-stream'
            ext = _EXT_BY_MIME.get(mime, os.path.splitext(media_ref.get('filename') or '')[1])
            stored = f'{uuid.uuid4().hex}{ext}'
            folder = current_app.config['INBOX_MEDIA_FOLDER']
            os.makedirs(folder, exist_ok=True)
            await client.download_media(message, file=os.path.join(folder, stored))
            return stored, mime
        finally:
            await client.disconnect()

    # --- outbound ----------------------------------------------------------
    def send_text(self, channel, external_chat_id: str, text: str) -> SentResult:
        return asyncio.run(self._send_async(channel, external_chat_id, text=text))

    def send_media(self, channel, external_chat_id: str, file_path: str,
                   caption: str | None = None) -> SentResult:
        return asyncio.run(self._send_async(channel, external_chat_id, file_path=file_path, caption=caption))

    async def _send_async(self, channel, external_chat_id: str, text: str | None = None,
                           file_path: str | None = None, caption: str | None = None) -> SentResult:
        try:
            client = client_for(channel)
        except RuntimeError as exc:
            return SentResult(ok=False, error=str(exc))

        await client.connect()
        try:
            chat_id = int(external_chat_id)
            if file_path:
                sent = await client.send_file(chat_id, file_path, caption=caption)
            else:
                sent = await client.send_message(chat_id, text)
            return SentResult(ok=True, external_message_id=str(sent.id))
        except Exception as exc:  # noqa: BLE001
            return SentResult(ok=False, error=str(exc))
        finally:
            await client.disconnect()

    # --- start new conversation (not a Protocol method — duck-typed, see
    # inbox_service.start_conversation) ----------------------------------
    def resolve_contact(self, channel, query: str) -> dict:
        return asyncio.run(self._resolve_contact_async(channel, query))

    async def _resolve_contact_async(self, channel, query: str) -> dict:
        from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
        from telethon.tl.types import InputPhoneContact

        client = client_for(channel)
        await client.connect()
        try:
            query = query.strip()
            if query.startswith('@'):
                entity = await client.get_entity(query.lstrip('@'))
            else:
                phone = query if query.startswith('+') else f'+{query}'
                result = await client(ImportContactsRequest([
                    InputPhoneContact(client_id=0, phone=phone, first_name='CRM', last_name='Contact'),
                ]))
                if not result.users:
                    raise RuntimeError('Номер не знайдено в Telegram')
                entity = result.users[0]
                try:
                    await client(DeleteContactsRequest([entity]))
                except Exception:  # noqa: BLE001 — best-effort cleanup, not fatal
                    pass

            name = ' '.join(p for p in [getattr(entity, 'first_name', None),
                                         getattr(entity, 'last_name', None)] if p) or None
            return {
                'external_chat_id': str(entity.id),
                'name': name,
                'username': getattr(entity, 'username', None),
                'phone': getattr(entity, 'phone', None),
            }
        finally:
            await client.disconnect()

    # --- contact lookup (duck-typed, see inbox_service._get_or_create_conversation) ---
    def enrich_contact(self, channel, external_chat_id: str) -> dict:
        """Best-effort name/username/phone lookup by chat id. Never raises.

        No-op when called from inside a running event loop (the worker and the
        history backfill) — `asyncio.run` can't nest there, and both of those
        callers already resolve the contact themselves.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass  # no loop running — we can drive one
        else:
            return {}
        try:
            return asyncio.run(self._enrich_contact_async(channel, external_chat_id))
        except Exception:  # noqa: BLE001
            return {}

    async def _enrich_contact_async(self, channel, external_chat_id: str) -> dict:
        client = client_for(channel)
        await client.connect()
        try:
            entity = await client.get_entity(int(external_chat_id))
            return contact_from_entity(entity)
        finally:
            await client.disconnect()

    # --- config --------------------------------------------------------
    def register_webhook(self, channel, webhook_url: str) -> None:
        pass  # no webhook for this channel type
