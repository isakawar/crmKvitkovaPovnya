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
# Separate channel: commands *to* the telegram_personal worker, never
# forwarded to the browser (the /inbox/stream route only subscribes to
# CHANNEL above).
BACKFILL_CHANNEL = 'inbox:backfill'


def _redis():
    return redis_lib.from_url(current_app.config['REDIS_URL'])


def publish(event_type: str, channel_id: int, conversation_id: int | None = None, **extra) -> None:
    try:
        _redis().publish(CHANNEL, json.dumps({
            'type': event_type,
            'channel_id': channel_id,
            'conversation_id': conversation_id,
            **extra,
        }))
    except Exception:  # noqa: BLE001
        log.exception('inbox event publish failed')


def publish_backfill_request(channel_id: int, conversation_id: int, days: int) -> None:
    """Ask the already-connected telegram_personal worker to pull older
    history for one conversation. Fire-and-forget — the worker publishes a
    `backfill_done`/`backfill_error` event on CHANNEL once it's done, no
    second MTProto connection is ever opened (see telegram_personal_backfill
    module docstring for why that matters)."""
    try:
        _redis().publish(BACKFILL_CHANNEL, json.dumps({
            'channel_id': channel_id,
            'conversation_id': conversation_id,
            'days': days,
        }))
    except Exception:  # noqa: BLE001
        log.exception('inbox backfill request publish failed')
