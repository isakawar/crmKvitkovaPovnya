"""Redis pub/sub fan-out so the inbox UI gets pushed updates instead of
waiting for its next poll. Best-effort — a publish failure must never break
message ingestion or sending, so every call swallows its own exceptions.
"""
from __future__ import annotations

import json
import logging

import redis as redis_lib
from flask import current_app

log = logging.getLogger(__name__)

CHANNEL = 'inbox:events'


def _redis():
    return redis_lib.from_url(current_app.config['REDIS_URL'])


def publish(event_type: str, channel_id: int, conversation_id: int | None = None) -> None:
    try:
        _redis().publish(CHANNEL, json.dumps({
            'type': event_type,
            'channel_id': channel_id,
            'conversation_id': conversation_id,
        }))
    except Exception:  # noqa: BLE001
        log.exception('inbox event publish failed')
