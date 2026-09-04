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

    @client.on(events.NewMessage(incoming=True))
    async def _on_message(event):
        with app.app_context():
            from app.models.messaging_channel import MessagingChannel
            ch = MessagingChannel.query.get(channel_id)
            if not ch or not ch.is_active:
                return
            try:
                inbound = build_inbound_event(event.message)
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


async def main_async(app):
    with app.app_context():
        from app.models.messaging_channel import MessagingChannel
        channel_ids = [
            c.id for c in MessagingChannel.query.filter_by(
                channel_type='telegram_personal', is_active=True,
            ).all()
            if c.session_encrypted
        ]

    if not channel_ids:
        logger.info('No active telegram_personal channels — sleeping')
        while True:
            await asyncio.sleep(60)

    await asyncio.gather(*(run_channel(app, cid) for cid in channel_ids))


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
