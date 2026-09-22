"""Channel adapter contract shared by all messaging channels.

An adapter translates between a provider (Telegram, Instagram, ...) and the
channel-agnostic domain layer (`inbox_service`). Adapters never touch the DB.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class InboundEvent:
    """One normalized event parsed from a provider webhook payload."""
    kind: str  # 'message' | 'connection' | 'edited' | 'deleted' | 'read' | 'reactions'
    external_chat_id: str = ''
    external_message_id: str | None = None
    text: str | None = None
    contact: dict = field(default_factory=dict)   # {name, username, phone}
    media: list[dict] = field(default_factory=list)  # [{type, tg_file_id, mime, filename}]
    date: datetime | None = None
    # True for a message the account owner sent themselves, outside the CRM
    # (telegram_personal is a real account — they also write from their phone).
    outgoing: bool = False
    # Telegram album id: several messages that belong to one album are merged
    # into a single Message with several media entries.
    group_id: str | None = None
    # kind == 'connection'
    connection_id: str | None = None
    connection_enabled: bool = True
    # kind == 'deleted'
    deleted_message_ids: list[str] = field(default_factory=list)
    # kind == 'read' — Telegram reports "read up to this id", never a per-message
    # timestamp. `read_inbox` means the account owner read the chat elsewhere;
    # otherwise the contact read what we sent them.
    read_max_id: int | None = None
    read_inbox: bool = False
    # kind == 'reactions' — the whole current set for `external_message_id`
    reactions: list[dict] = field(default_factory=list)


@dataclass
class SentResult:
    ok: bool
    external_message_id: str | None = None
    error: str | None = None


class ChannelAdapter(Protocol):
    channel_type: str

    def verify_webhook(self, request, channel) -> bool:
        """Authenticate an inbound webhook POST (secret token / HMAC signature)."""
        ...

    def verify_subscription(self, args, channel) -> str | None:
        """Handle a provider's GET verification handshake. Return the challenge
        string to echo, or None when this provider has no GET handshake."""
        ...

    def parse_events(self, payload: dict) -> list[InboundEvent]: ...

    def send_text(self, channel, external_chat_id: str, text: str) -> SentResult: ...

    def send_media(self, channel, external_chat_id: str, file_path: str,
                   caption: str | None = None) -> SentResult: ...

    def download_media(self, channel, media_ref: dict) -> tuple[str, str]:
        """Return (stored_filename, mime_type). Raises on failure."""
        ...

    def register_webhook(self, channel, webhook_url: str) -> None: ...


def get_adapter(channel) -> ChannelAdapter:
    """Resolve the adapter for a MessagingChannel by its channel_type."""
    ctype = getattr(channel, 'channel_type', channel)
    if ctype == 'telegram':
        from app.services.messaging.telegram_business import TelegramBusinessAdapter
        return TelegramBusinessAdapter()
    if ctype == 'instagram':
        from app.services.messaging.instagram_dm import InstagramDMAdapter
        return InstagramDMAdapter()
    if ctype == 'telegram_personal':
        from app.services.messaging.telegram_personal import TelegramPersonalAdapter
        return TelegramPersonalAdapter()
    if ctype == 'viber':
        from app.services.messaging.viber import ViberAdapter
        return ViberAdapter()
    if ctype == 'whatsapp':
        from app.services.messaging.whatsapp import WhatsAppAdapter
        return WhatsAppAdapter()
    raise ValueError(f'No messaging adapter for channel_type={ctype!r}')
