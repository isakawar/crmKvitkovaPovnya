"""WhatsApp adapter — WhatsApp Business Platform (Cloud API), connected via the
same Facebook Login for Business / Embedded Signup flow used for Instagram.

Unlike Instagram (Page-linked), a WhatsApp number is registered under a
WhatsApp Business Account (WABA), not a Facebook Page — so the connect step
(see app/blueprints/settings/routes.py messaging_whatsapp_complete) uses
Meta's Embedded Signup JS popup instead of the Page picker, and channel
credentials come back from that popup (code + waba_id + phone_number_id)
rather than from `/me/accounts`.

  channel.external_id              — WhatsApp phone_number_id (used in the send URL)
  channel.wa_waba_id               — WhatsApp Business Account id (used to subscribe webhooks)
  channel.wa_access_token_encrypted — long-lived token from Embedded Signup, Fernet-encrypted
  INBOX_INSTAGRAM_APP_SECRET (env) — same Meta App secret, verifies X-Hub-Signature-256

Constraints (Meta): 24h customer-service messaging window for free-form text
replies outside that window a pre-approved template message is required —
not implemented here (text/media replies only, v1).
"""
from __future__ import annotations

import os
import uuid

import requests
from flask import current_app

from app.services.messaging import session_crypto
from app.services.messaging.adapter import InboundEvent, SentResult

_TIMEOUT = 30


def _cfg(key: str) -> str:
    return current_app.config.get(key, '')


def _graph_root() -> str:
    return f'https://graph.facebook.com/{_cfg("INBOX_INSTAGRAM_GRAPH_VERSION") or "v23.0"}'


def _token(channel) -> str:
    if not channel.wa_access_token_encrypted:
        raise RuntimeError('Канал не підключено через Facebook — перепідключіть у /settings/messaging')
    return session_crypto.decrypt(channel.wa_access_token_encrypted)


def _auth_headers(channel) -> dict:
    return {'Authorization': f'Bearer {_token(channel)}'}


class WhatsAppAdapter:
    channel_type = 'whatsapp'

    # --- inbound -----------------------------------------------------------
    def verify_subscription(self, args, channel) -> str | None:
        if (args.get('hub.mode') == 'subscribe'
                and args.get('hub.verify_token')
                and args.get('hub.verify_token') == channel.webhook_secret):
            return args.get('hub.challenge') or ''
        return None

    def verify_webhook(self, request, channel) -> bool:
        import hashlib
        import hmac
        secret = _cfg('INBOX_INSTAGRAM_APP_SECRET')
        header = request.headers.get('X-Hub-Signature-256', '')
        if not secret or not header.startswith('sha256='):
            return False
        expected = hmac.new(secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(header.split('=', 1)[1], expected)

    def parse_events(self, payload: dict) -> list[InboundEvent]:
        if not isinstance(payload, dict) or payload.get('object') != 'whatsapp_business_account':
            return []
        events: list[InboundEvent] = []
        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value') or {}
                if change.get('field') != 'messages' or not value.get('messages'):
                    continue  # skip status/delivery-receipt updates
                profiles = {c.get('wa_id'): (c.get('profile') or {}).get('name')
                            for c in value.get('contacts', [])}
                for m in value['messages']:
                    sender = m.get('from', '')
                    text, media = None, []
                    mtype = m.get('type')
                    if mtype == 'text':
                        text = (m.get('text') or {}).get('body')
                    elif mtype in ('image', 'video', 'audio', 'document', 'voice', 'sticker'):
                        att = m.get(mtype) or {}
                        if att.get('id'):
                            media.append({
                                'type': 'photo' if mtype == 'image' else ('voice' if mtype in ('audio', 'voice') else mtype),
                                'media_id': att['id'], 'mime': att.get('mime_type'),
                                'filename': att.get('filename'),
                            })
                        text = att.get('caption')
                    events.append(InboundEvent(
                        kind='message',
                        external_chat_id=sender,
                        external_message_id=m.get('id'),
                        text=text,
                        contact={'name': profiles.get(sender), 'phone': sender},
                        media=media,
                    ))
        return events

    def download_media(self, channel, media_ref: dict) -> tuple[str, str]:
        headers = _auth_headers(channel)
        meta = requests.get(f'{_graph_root()}/{media_ref["media_id"]}', headers=headers, timeout=_TIMEOUT)
        meta.raise_for_status()
        info = meta.json()
        resp = requests.get(info['url'], headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        mime = info.get('mime_type', 'application/octet-stream').split(';')[0]
        ext = {
            'image/jpeg': '.jpg', 'image/png': '.png', 'video/mp4': '.mp4',
            'audio/ogg': '.ogg', 'audio/mpeg': '.mp3', 'application/pdf': '.pdf',
        }.get(mime, os.path.splitext(media_ref.get('filename') or '')[1])
        stored = f'{uuid.uuid4().hex}{ext}'
        folder = current_app.config['INBOX_MEDIA_FOLDER']
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, stored), 'wb') as fh:
            fh.write(resp.content)
        return stored, mime

    # --- outbound --------------------------------------------------------
    def send_text(self, channel, external_chat_id: str, text: str) -> SentResult:
        try:
            headers = _auth_headers(channel)
        except RuntimeError as exc:
            return SentResult(ok=False, error=str(exc))
        try:
            r = requests.post(
                f'{_graph_root()}/{channel.external_id}/messages',
                headers=headers,
                json={'messaging_product': 'whatsapp', 'to': external_chat_id,
                      'type': 'text', 'text': {'body': text}},
                timeout=_TIMEOUT,
            )
            body = r.json()
            if r.status_code >= 400 or body.get('error'):
                err = (body.get('error') or {}).get('message') or f'HTTP {r.status_code}'
                return SentResult(ok=False, error=err)
            msg_id = ((body.get('messages') or [{}])[0]).get('id', '')
            return SentResult(ok=True, external_message_id=msg_id)
        except Exception as exc:  # noqa: BLE001
            return SentResult(ok=False, error=str(exc))

    def send_media(self, channel, external_chat_id: str, file_path: str,
                   caption: str | None = None) -> SentResult:
        return SentResult(
            ok=False,
            error='WhatsApp: надсилання файлів поки не підтримується',
        )

    # --- config ---------------------------------------------------------
    def register_webhook(self, channel, webhook_url: str) -> None:
        """Subscribe this WABA to the App's webhook (the callback URL itself is
        configured once, app-wide, in the Meta App Dashboard by the developer)."""
        headers = _auth_headers(channel)
        r = requests.post(
            f'{_graph_root()}/{channel.wa_waba_id}/subscribed_apps',
            headers=headers, timeout=_TIMEOUT,
        )
        body = r.json()
        if r.status_code >= 400 or body.get('error'):
            err = (body.get('error') or {}).get('message') or f'HTTP {r.status_code}'
            raise RuntimeError(err)
