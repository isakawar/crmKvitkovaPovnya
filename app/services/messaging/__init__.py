"""Omnichannel inbox: channel adapters + domain logic.

Public entry points:
  - get_adapter(channel) -> ChannelAdapter
  - inbox_service.*  (ingest_event, send_reply, list_conversations, ...)
  - channel_config_service.*  (CRUD channels + access, register_webhook)
"""
from app.services.messaging.adapter import (
    ChannelAdapter, InboundEvent, SentResult, get_adapter,
)

__all__ = ['ChannelAdapter', 'InboundEvent', 'SentResult', 'get_adapter']
