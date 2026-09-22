"""Viber Bot adapter (REST Bot API, https://developers.viber.com/docs/api/rest-bot-api/).

Constraints (Viber): outbound picture/video messages require a publicly
reachable URL for the media (Viber's servers fetch it themselves) — we have
no unauthenticated file host for locally-uploaded replies, so v1 sends text
only, same call already made for Instagram in `instagram_dm.py` and for the
same underlying reason.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import uuid

import requests
from flask import current_app

from app.services.messaging.adapter import InboundEvent, SentResult

API_ROOT = 'https://chatapi.viber.com/pa'
_TIMEOUT = 30
_TYPE_MAP = {'picture': 'photo', 'video': 'video', 'file': 'document'}
_EXT_BY_MIME = {
    'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
    'video/mp4': '.mp4',
}


def _token() -> str:
    token = current_app.config.get('INBOX_VIBER_BOT_TOKEN', '')
    if not token:
        raise RuntimeError('INBOX_VIBER_BOT_TOKEN is not configured')
    return token


def _api(method: str, **payload) -> dict:
    url = f'{API_ROOT}/{method}'
    resp = requests.post(url, json=payload, timeout=_TIMEOUT,
                         headers={'X-Viber-Auth-Token': _token()})
    data = resp.json()
    if data.get('status') != 0:
        raise ViberApiError(data.get('status_message') or f'HTTP {resp.status_code}')
    return data


class ViberApiError(RuntimeError):
    pass


def _media_from_message(msg: dict) -> list[dict]:
    mtype = _TYPE_MAP.get(msg.get('type'))
    if not mtype or not msg.get('media'):
        return []
    return [{'type': mtype, 'url': msg['media'], 'mime': None,
             'filename': msg.get('file_name')}]


class ViberAdapter:
    channel_type = 'viber'

    # --- inbound -----------------------------------------------------------
    def verify_webhook(self, request, channel) -> bool:
        got = request.headers.get('X-Viber-Content-Signature', '')
        expected = hmac.new(_token().encode(), request.get_data(), hashlib.sha256).hexdigest()
        return bool(got) and hmac.compare_digest(got, expected)

    def verify_subscription(self, args, channel) -> str | None:
        return None  # Viber has no GET verification handshake

    def parse_events(self, payload: dict) -> list[InboundEvent]:
        if not isinstance(payload, dict):
            return []
        if payload.get('event') != 'message':
            return []  # subscribed/unsubscribed/conversation_started/delivered/seen/failed carry no content

        sender = payload.get('sender') or {}
        msg = payload.get('message') or {}
        text = msg.get('text')
        media = _media_from_message(msg)
        if not text and not media:
            text = '[непідтримуваний тип повідомлення]'

        timestamp = payload.get('timestamp')
        from datetime import datetime
        date = datetime.fromtimestamp(timestamp / 1000) if timestamp else None

        return [InboundEvent(
            kind='message',
            external_chat_id=str(sender.get('id', '')),
            external_message_id=str(payload.get('message_token', '')),
            text=text,
            contact={'name': sender.get('name'), 'username': None, 'phone': None},
            media=media,
            date=date,
        )]

    def download_media(self, channel, media_ref: dict) -> tuple[str, str]:
        url = media_ref['url']
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()

        max_bytes = current_app.config.get('INBOX_MEDIA_MAX_BYTES', 15 * 1024 * 1024)
        if len(resp.content) > max_bytes:
            raise RuntimeError(f'media too large: {len(resp.content)} bytes')

        mime = media_ref.get('mime') or resp.headers.get('Content-Type') or 'application/octet-stream'
        ext = (os.path.splitext(url.split('?')[0])[1]
               or _EXT_BY_MIME.get(mime, ''))
        stored = f'{uuid.uuid4().hex}{ext}'
        folder = current_app.config['INBOX_MEDIA_FOLDER']
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, stored), 'wb') as fh:
            fh.write(resp.content)
        return stored, mime

    # --- outbound --------------------------------------------------------
    def send_text(self, channel, external_chat_id: str, text: str,
                 reply_to_external_id: str | None = None) -> SentResult:
        try:
            result = _api('send_message', receiver=external_chat_id, type='text',
                          text=text, sender={'name': channel.name[:28]})
            return SentResult(ok=True, external_message_id=str(result.get('message_token')))
        except ViberApiError as exc:
            return SentResult(ok=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return SentResult(ok=False, error=str(exc))

    def send_media(self, channel, external_chat_id: str, file_path: str,
                   caption: str | None = None, reply_to_external_id: str | None = None) -> SentResult:
        return SentResult(ok=False, error='Viber: надсилання файлів поки не підтримується '
                                          '(Viber вимагає публічний URL для медіа)')

    # --- config ---------------------------------------------------------
    def register_webhook(self, channel, webhook_url: str) -> None:
        _api('set_webhook', url=webhook_url,
             event_types=['message', 'subscribed', 'unsubscribed', 'conversation_started'])
