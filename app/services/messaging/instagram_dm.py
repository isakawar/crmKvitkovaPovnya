"""Instagram Direct adapter — Instagram API with Instagram Login.

Uses graph.instagram.com directly (no Facebook Page). One IG Professional
account per channel. Credentials come from env:
  INBOX_INSTAGRAM_ACCESS_TOKEN  — long-lived IG user token (refreshable, ~60d)
  INBOX_INSTAGRAM_APP_SECRET    — Meta app secret, for X-Hub-Signature-256

The channel's `webhook_secret` doubles as the `hub.verify_token` for the
GET subscription handshake. `channel.external_id` holds the IG account id
(needed as the path when sending), learned from the first webhook `entry.id`.

Constraints (Meta): replies are only deliverable within 24h of the user's
last message (standard messaging window). Outbound attachments require a
publicly reachable URL, so v1 sends text only.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import uuid

import requests
from flask import current_app

from app.services.messaging.adapter import InboundEvent, SentResult

_TIMEOUT = 30
_ATTACH_TYPE = {'image': 'photo', 'video': 'video', 'audio': 'voice', 'file': 'document'}


def _cfg(key: str) -> str:
    return current_app.config.get(key, '')


def _graph_root() -> str:
    return f'https://graph.instagram.com/{_cfg("INBOX_INSTAGRAM_GRAPH_VERSION") or "v23.0"}'


class InstagramDMAdapter:
    channel_type = 'instagram'

    # --- inbound -----------------------------------------------------------
    def verify_subscription(self, args, channel) -> str | None:
        if (args.get('hub.mode') == 'subscribe'
                and args.get('hub.verify_token')
                and args.get('hub.verify_token') == channel.webhook_secret):
            return args.get('hub.challenge') or ''
        return None

    def verify_webhook(self, request, channel) -> bool:
        secret = _cfg('INBOX_INSTAGRAM_APP_SECRET')
        header = request.headers.get('X-Hub-Signature-256', '')
        if not secret or not header.startswith('sha256='):
            return False
        expected = hmac.new(secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(header.split('=', 1)[1], expected)

    def parse_events(self, payload: dict) -> list[InboundEvent]:
        if not isinstance(payload, dict) or payload.get('object') != 'instagram':
            return []
        events: list[InboundEvent] = []
        for entry in payload.get('entry', []):
            account_id = str(entry.get('id', ''))
            for m in entry.get('messaging', []):
                msg = m.get('message')
                if not msg or msg.get('is_echo') or msg.get('is_deleted'):
                    continue  # echoes of our own sends / deletes — skip in v1
                sender = str((m.get('sender') or {}).get('id', ''))
                media = []
                for att in msg.get('attachments', []) or []:
                    url = (att.get('payload') or {}).get('url')
                    if url:
                        media.append({
                            'type': _ATTACH_TYPE.get(att.get('type'), 'document'),
                            'url': url, 'mime': None, 'filename': None,
                        })
                events.append(InboundEvent(
                    kind='message',
                    external_chat_id=sender,
                    external_message_id=str(msg.get('mid')),
                    text=msg.get('text'),
                    contact={'name': None, 'username': None, 'phone': None,
                             '_account_id': account_id},
                    media=media,
                ))
        return events

    def download_media(self, channel, media_ref: dict) -> tuple[str, str]:
        url = media_ref['url']
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        mime = resp.headers.get('Content-Type', 'application/octet-stream').split(';')[0]
        ext = os.path.splitext(url.split('?')[0])[1] or {
            'image/jpeg': '.jpg', 'image/png': '.png', 'video/mp4': '.mp4',
            'audio/mp4': '.m4a',
        }.get(mime, '')
        stored = f'{uuid.uuid4().hex}{ext}'
        folder = current_app.config['INBOX_MEDIA_FOLDER']
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, stored), 'wb') as fh:
            fh.write(resp.content)
        return stored, mime

    def enrich_contact(self, channel, external_chat_id: str) -> dict:
        """Best-effort profile lookup (name/username). Never raises."""
        token = _cfg('INBOX_INSTAGRAM_ACCESS_TOKEN')
        if not token:
            return {}
        try:
            r = requests.get(f'{_graph_root()}/{external_chat_id}',
                             params={'fields': 'name,username', 'access_token': token},
                             timeout=_TIMEOUT)
            data = r.json()
            return {'name': data.get('name'), 'username': data.get('username')}
        except Exception:  # noqa: BLE001
            return {}

    # --- outbound --------------------------------------------------------
    def send_text(self, channel, external_chat_id: str, text: str) -> SentResult:
        token = _cfg('INBOX_INSTAGRAM_ACCESS_TOKEN')
        if not token:
            return SentResult(ok=False, error='INBOX_INSTAGRAM_ACCESS_TOKEN не налаштовано')
        account_id = channel.external_id or 'me'
        try:
            r = requests.post(
                f'{_graph_root()}/{account_id}/messages',
                params={'access_token': token},
                json={'recipient': {'id': external_chat_id},
                      'message': {'text': text}},
                timeout=_TIMEOUT,
            )
            body = r.json()
            if r.status_code >= 400 or body.get('error'):
                err = (body.get('error') or {}).get('message') or f'HTTP {r.status_code}'
                return SentResult(ok=False, error=err)
            return SentResult(ok=True, external_message_id=str(body.get('message_id') or ''))
        except Exception as exc:  # noqa: BLE001
            return SentResult(ok=False, error=str(exc))

    def send_media(self, channel, external_chat_id: str, file_path: str,
                   caption: str | None = None) -> SentResult:
        return SentResult(
            ok=False,
            error='Instagram: надсилання фото поки не підтримується (потрібен публічний URL)',
        )

    # --- config ---------------------------------------------------------
    def register_webhook(self, channel, webhook_url: str) -> None:
        """Instagram webhooks are configured in the Meta App dashboard, not via
        an API call. This is a no-op; the URL/verify-token are shown in the UI."""
        return None

    def refresh_token(self) -> dict:
        token = _cfg('INBOX_INSTAGRAM_ACCESS_TOKEN')
        r = requests.get(f'{_graph_root()}/refresh_access_token',
                         params={'grant_type': 'ig_refresh_token', 'access_token': token},
                         timeout=_TIMEOUT)
        return r.json()
