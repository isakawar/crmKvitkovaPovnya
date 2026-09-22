#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Persistent MTProto client(s) for "personal number" Telegram channels.

One Telethon client per active `telegram_personal` channel, all sharing one
asyncio event loop. Each client pushes inbound messages straight into
`inbox_service.ingest_event` from inside the Flask app context — this
channel type has no HTTP webhook (see app/services/messaging/telegram_personal.py).

WARNING: each client logs in as a real personal Telegram account, not a bot.
"""
import asyncio
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/telegram_personal_worker.log', encoding='utf-8')
        if os.path.exists('/app/logs') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)


def wait_for_database():
    max_retries = 30
    for attempt in range(1, max_retries + 1):
        try:
            app = create_app()
            with app.app_context():
                from app.extensions import db
                with db.engine.connect() as conn:
                    conn.execute(db.text('SELECT 1'))
                logger.info('Database connection successful')
                return app
        except Exception as exc:
            logger.warning('Database not ready (attempt %s/%s): %s', attempt, max_retries, exc)
            time.sleep(2)
    raise RuntimeError('Could not connect to database after maximum retries')


async def run_channel(app, channel_id: int):
    """Connect one channel's client and forward its messages until disconnected."""
    from telethon import events
    from app.services.messaging.telegram_personal import client_for, build_inbound_event
    from app.services.messaging import inbox_service

    with app.app_context():
        from app.models.messaging_channel import MessagingChannel
        channel = MessagingChannel.query.get(channel_id)
        if not channel or not channel.session_encrypted:
            logger.warning('Channel #%s has no session, skipping', channel_id)
            return
        client = client_for(channel)

    # outgoing=True as well: this is a real account, so the owner also writes
    # from their phone, and without it the CRM thread has one side missing.
    # A reply sent from the CRM comes back here too and is dropped by
    # inbox_service's external_message_id guard.
    @client.on(events.NewMessage(incoming=True, outgoing=True))
    async def _on_message(event):
        if not event.is_private:
            return  # skip channel posts / group messages — inbox is 1:1 only
        # Only here, inside the live loop, can the peer be resolved cheaply —
        # without it the conversation has no name, can't be matched to a client,
        # and its media can't be downloaded later.
        try:
            peer = await event.get_chat()
        except Exception:
            logger.exception('Channel #%s: failed to resolve chat', channel_id)
            peer = None
        with app.app_context():
            from app.models.messaging_channel import MessagingChannel
            ch = MessagingChannel.query.get(channel_id)
            if not ch or not ch.is_active:
                return
            try:
                inbound = build_inbound_event(event.message, peer=peer)
                msg = inbox_service.ingest_event(ch, inbound)
                if msg is not None and inbound.media:
                    inbox_service.prefetch_message_media(app, msg.id)
            except Exception:
                logger.exception('Channel #%s: failed to ingest message', channel_id)

    await client.connect()
    if not await client.is_user_authorized():
        logger.error('Channel #%s: session not authorized, skipping', channel_id)
        await client.disconnect()
        return
    logger.info('Channel #%s: listening for incoming messages', channel_id)
    await client.run_until_disconnected()


POLL_INTERVAL_SECONDS = 20


def _active_channel_ids(app) -> set[int]:
    with app.app_context():
        from app.models.messaging_channel import MessagingChannel
        return {
            c.id for c in MessagingChannel.query.filter_by(
                channel_type='telegram_personal', is_active=True,
            ).all()
            if c.session_encrypted
        }


async def main_async(app):
    """Supervisor loop: periodically re-scans for channels connected/deleted/
    deactivated since startup — a channel authorized through the settings UI
    while this process is already running must not require a manual restart."""
    running: dict[int, asyncio.Task] = {}

    while True:
        wanted = _active_channel_ids(app)

        for channel_id in wanted - running.keys():
            logger.info('Channel #%s: starting listener', channel_id)
            running[channel_id] = asyncio.create_task(run_channel(app, channel_id))

        for channel_id in list(running.keys() - wanted):
            logger.info('Channel #%s: no longer active, stopping listener', channel_id)
            running.pop(channel_id).cancel()

        for channel_id, task in list(running.items()):
            if task.done():
                exc = task.exception() if not task.cancelled() else None
                if exc:
                    logger.error('Channel #%s: listener crashed: %s', channel_id, exc)
                running.pop(channel_id)

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def main():
    logger.info('=== TELEGRAM PERSONAL WORKER ===')
    logger.info('Waiting for database connection...')
    app = wait_for_database()
    try:
        asyncio.run(main_async(app))
    except KeyboardInterrupt:
        logger.info('Stopped by user (Ctrl+C)')
    except Exception:
        logger.exception('Fatal error')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
