"""Login handshake for a "personal number" Telegram channel (MTProto/Telethon).

WARNING: this authenticates as a real personal Telegram account, not a bot.
Automating a personal account is outside what Telegram's client API is meant
for, and Telegram may limit/restrict an account it flags as automated. Use a
dedicated number for this, not the owner's primary personal number.

Three-step flow, each step is a short-lived connection (no client kept alive
between requests — Flask views are stateless, so the not-yet-authorized
StringSession is round-tripped through `pending_session_encrypted`):

  1. request_code(channel, phone)     -> sends the Telegram login code
  2. confirm_code(channel, code)      -> may raise NeedsPasswordError (2FA)
  3. confirm_password(channel, password) -> only if step 2 needed a password

On success (from step 2 or 3), `channel.session_encrypted`/`external_id` are
set and `pending_*` fields are cleared — the caller must db.session.commit().
"""
from __future__ import annotations

import asyncio

from flask import current_app
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

from app.services.messaging import session_crypto


class NeedsPasswordError(Exception):
    """Raised by confirm_code when the account has 2FA enabled."""


def _api_creds() -> tuple[int, str]:
    api_id = current_app.config.get('MESSAGING_TG_API_ID')
    api_hash = current_app.config.get('MESSAGING_TG_API_HASH')
    if not api_id or not api_hash:
        raise RuntimeError('MESSAGING_TG_API_ID/MESSAGING_TG_API_HASH не налаштовано')
    return int(api_id), api_hash


def _client_from(session_str: str = '') -> TelegramClient:
    api_id, api_hash = _api_creds()
    return TelegramClient(StringSession(session_str), api_id, api_hash)


async def _request_code_async(phone: str) -> tuple[str, str]:
    client = _client_from()
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
        return client.session.save(), sent.phone_code_hash
    finally:
        await client.disconnect()


def request_code(channel, phone: str) -> None:
    session_str, phone_code_hash = asyncio.run(_request_code_async(phone))
    channel.phone_number = phone.strip()
    channel.pending_phone_code_hash = phone_code_hash
    channel.pending_session_encrypted = session_crypto.encrypt(session_str)


async def _sign_in_async(pending_session: str, **kwargs) -> tuple[str, int]:
    client = _client_from(pending_session)
    await client.connect()
    try:
        await client.sign_in(**kwargs)
        me = await client.get_me()
        return client.session.save(), me.id
    finally:
        await client.disconnect()


def confirm_code(channel, code: str) -> None:
    pending_session = session_crypto.decrypt(channel.pending_session_encrypted)
    try:
        session_str, user_id = asyncio.run(_sign_in_async(
            pending_session,
            phone=channel.phone_number,
            code=code,
            phone_code_hash=channel.pending_phone_code_hash,
        ))
    except SessionPasswordNeededError:
        raise NeedsPasswordError() from None
    _finish_login(channel, session_str, user_id)


def confirm_password(channel, password: str) -> None:
    pending_session = session_crypto.decrypt(channel.pending_session_encrypted)
    session_str, user_id = asyncio.run(_sign_in_async(pending_session, password=password))
    _finish_login(channel, session_str, user_id)


def _finish_login(channel, session_str: str, user_id: int) -> None:
    channel.session_encrypted = session_crypto.encrypt(session_str)
    channel.external_id = str(user_id)
    channel.is_active = True
    channel.pending_session_encrypted = None
    channel.pending_phone_code_hash = None
