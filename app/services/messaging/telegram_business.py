"""Telegram Business API adapter.

Uses the plain Bot API over HTTPS (no python-telegram-bot / asyncio). The bot
is connected to the owner's Telegram Business account; messages clients send to
that personal account arrive as `business_message` updates, and replies are sent
with `business_connection_id` so they appear from the account owner.
"""
from __future__ import annotations

import hmac
import os
import uuid
from datetime import datetime, timezone

import requests
from flask import current_app

from app.services.messaging.adapter import InboundEvent, SentResult

API_ROOT = 'https://api.telegram.org'
_TIMEOUT = 30

_EXT_BY_MIME = {
    'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
    'audio/ogg': '.ogg', 'video/mp4': '.mp4',
}


def _token() -> str:
    token = current_app.config.get('INBOX_TELEGRAM_BOT_TOKEN', '')
    if not token:
        raise RuntimeError('INBOX_TELEGRAM_BOT_TOKEN is not configured')
    return token


def _api(method: str, **payload) -> dict:
    url = f'{API_ROOT}/bot{_token()}/{method}'
    resp = requests.post(url, json=payload, timeout=_TIMEOUT)
    data = resp.json()
    if not data.get('ok'):
        raise TelegramApiError(data.get('description') or f'HTTP {resp.status_code}',
                               error_code=data.get('error_code'))
    return data['result']


class TelegramApiError(RuntimeError):
    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code


def _dt(ts) -> datetime | None:
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(tzinfo=None)


def _contact_from(user: dict) -> dict:
    if not user:
        return {}
    name = ' '.join(p for p in [user.get('first_name'), user.get('last_name')] if p).strip()
    return {
        'name': name or None,
        'username': user.get('username'),
        'phone': None,
    }


def _media_from_message(msg: dict) -> list[dict]:
    media = []
    if msg.get('photo'):
        largest = max(msg['photo'], key=lambda p: p.get('file_size', 0))
        media.append({'type': 'photo', 'tg_file_id': largest['file_id'],
                      'mime': 'image/jpeg', 'filename': None,
                      'size': largest.get('file_size')})
    doc = msg.get('document')
    if doc:
        media.append({'type': 'document', 'tg_file_id': doc['file_id'],
                      'mime': doc.get('mime_type') or 'application/octet-stream',
                      'filename': doc.get('file_name'), 'size': doc.get('file_size')})
    voice = msg.get('voice')
    if voice:
        media.append({'type': 'voice', 'tg_file_id': voice['file_id'],
                      'mime': voice.get('mime_type') or 'audio/ogg',
                      'filename': None, 'size': voice.get('file_size')})
    video = msg.get('video')
    if video:
        media.append({'type': 'video', 'tg_file_id': video['file_id'],
                      'mime': video.get('mime_type') or 'video/mp4',
                      'filename': video.get('file_name'), 'size': video.get('file_size')})
    return media


class TelegramBusinessAdapter:
    channel_type = 'telegram'

    # --- inbound -----------------------------------------------------------
    def verify_webhook(self, request, channel) -> bool:
        got = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        return bool(channel.webhook_secret) and hmac.compare_digest(got, channel.webhook_secret)

    def verify_subscription(self, args, channel) -> str | None:
        return None  # Telegram has no GET verification handshake

    def parse_events(self, payload: dict) -> list[InboundEvent]:
        if not isinstance(payload, dict):
            return []

        conn = payload.get('business_connection')
        if conn:
            return [InboundEvent(
                kind='connection',
                connection_id=str(conn.get('id')),
                connection_enabled=bool(conn.get('is_enabled', True)),
            )]

        deleted = payload.get('deleted_business_messages')
        if deleted:
            chat = deleted.get('chat') or {}
            return [InboundEvent(
                kind='deleted',
                external_chat_id=str(chat.get('id', '')),
                deleted_message_ids=[str(m) for m in deleted.get('message_ids', [])],
            )]

        msg = payload.get('business_message')
        edited = payload.get('edited_business_message')
        src = msg or edited
        if not src:
            return []

        chat = src.get('chat') or {}
        return [InboundEvent(
            kind='message' if msg else 'edited',
            external_chat_id=str(chat.get('id', '')),
            external_message_id=str(src.get('message_id')),
            text=src.get('text') or src.get('caption'),
            contact=_contact_from(src.get('from') or {}),
            media=_media_from_message(src),
            date=_dt(src.get('date')),
        )]

    def download_media(self, channel, media_ref: dict) -> tuple[str, str]:
        file_id = media_ref['tg_file_id']
        info = _api('getFile', file_id=file_id)
        max_bytes = current_app.config.get('INBOX_MEDIA_MAX_BYTES', 15 * 1024 * 1024)
        if info.get('file_size') and info['file_size'] > max_bytes:
            raise RuntimeError(f'media too large: {info["file_size"]} bytes')

        file_path = info['file_path']
        url = f'{API_ROOT}/file/bot{_token()}/{file_path}'
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()

        mime = media_ref.get('mime') or 'application/octet-stream'
        ext = (os.path.splitext(file_path)[1]
               or _EXT_BY_MIME.get(mime, ''))
        stored = f'{uuid.uuid4().hex}{ext}'
        folder = current_app.config['INBOX_MEDIA_FOLDER']
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, stored), 'wb') as fh:
            fh.write(resp.content)
        return stored, mime

    # --- outbound --------------------------------------------------------
    def send_text(self, channel, external_chat_id: str, text: str) -> SentResult:
        return self._send('sendMessage', channel, external_chat_id, {'text': text})

    def send_media(self, channel, external_chat_id: str, file_path: str,
                   caption: str | None = None) -> SentResult:
        if not channel.external_id:
            return SentResult(ok=False, error='Бот не підключений до Telegram Business акаунта')
        url = f'{API_ROOT}/bot{_token()}/sendPhoto'
        data = {'business_connection_id': channel.external_id, 'chat_id': external_chat_id}
        if caption:
            data['caption'] = caption
        try:
            with open(file_path, 'rb') as fh:
                resp = requests.post(url, data=data, files={'photo': fh}, timeout=_TIMEOUT)
            body = resp.json()
            if not body.get('ok'):
                return self._fail(channel, body.get('description') or f'HTTP {resp.status_code}')
            return SentResult(ok=True, external_message_id=str(body['result']['message_id']))
        except Exception as exc:  # noqa: BLE001
            return SentResult(ok=False, error=str(exc))

    def _send(self, method, channel, external_chat_id, extra) -> SentResult:
        if not channel.external_id:
            return SentResult(ok=False, error='Бот не підключений до Telegram Business акаунта')
        try:
            result = _api(method, business_connection_id=channel.external_id,
                          chat_id=external_chat_id, **extra)
            return SentResult(ok=True, external_message_id=str(result.get('message_id')))
        except TelegramApiError as exc:
            return self._fail(channel, str(exc))
        except Exception as exc:  # noqa: BLE001
            return SentResult(ok=False, error=str(exc))

    @staticmethod
    def _fail(channel, description: str) -> SentResult:
        if 'BUSINESS_CONNECTION' in description.upper() or 'connection' in description.lower():
            from app.extensions import db
            channel.is_active = False
            channel.external_id = None
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        return SentResult(ok=False, error=description)

    # --- config ---------------------------------------------------------
    def register_webhook(self, channel, webhook_url: str) -> None:
        _api('setWebhook',
             url=webhook_url,
             secret_token=channel.webhook_secret,
             allowed_updates=['business_connection', 'business_message',
                              'edited_business_message', 'deleted_business_messages'])
