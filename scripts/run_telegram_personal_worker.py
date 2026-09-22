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
    from telethon.tl.types import UpdateMessageReactions
    from app.services.messaging.telegram_personal import (
        build_inbound_event, build_reactions_event, build_read_event, client_for,
    )
    from app.services.messaging import inbox_service

    with app.app_context():
        from app.models.messaging_channel import MessagingChannel
        channel = MessagingChannel.query.get(channel_id)
        if not channel or not channel.session_encrypted:
            logger.warning('Channel #%s has no session, skipping', channel_id)
            return
        client = client_for(channel)

    def _ingest(inbound):
        """Push one already-built event into the inbox, inside an app context.

        Returns the ingested message's id, not the ORM object itself — the
        object is detached the moment this app context exits (Flask-SQLAlchemy
        tears the scoped session down on context pop), and accessing any of
        its attributes afterwards raises DetachedInstanceError. `msg.id` is
        read here, while the session is still alive.
        """
        with app.app_context():
            from app.models.messaging_channel import MessagingChannel
            ch = MessagingChannel.query.get(channel_id)
            if not ch or not ch.is_active:
                return None
            try:
                msg = inbox_service.ingest_event(ch, inbound)
                return msg.id if msg is not None else None
            except Exception:
                logger.exception('Channel #%s: failed to ingest %s', channel_id, inbound.kind)
                return None

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
        inbound = build_inbound_event(event.message, peer=peer)
        msg_id = _ingest(inbound)
        if msg_id is not None and inbound.media:
            inbox_service.prefetch_message_media(app, msg_id)

    # inbox=True fires when the owner reads the chat somewhere else (their
    # phone) — the CRM badge follows it; the default fires when the contact
    # reads what we sent, which is what turns a tick into "read".
    @client.on(events.MessageRead)
    @client.on(events.MessageRead(inbox=True))
    async def _on_read(event):
        if not event.is_private:
            return
        _ingest(build_read_event(event.chat_id, event.max_id, event.inbox))

    # Reactions have no high-level event — they arrive as a raw update carrying
    # the message's whole current reaction set.
    @client.on(events.Raw(types=UpdateMessageReactions))
    async def _on_reactions(update):
        _ingest(build_reactions_event(update))

    await client.connect()
    if not await client.is_user_authorized():
        logger.error('Channel #%s: session not authorized, skipping', channel_id)
        await client.disconnect()
        return
    logger.info('Channel #%s: listening for incoming messages', channel_id)
    backfill_task = asyncio.create_task(_listen_for_backfill(app, channel_id, client))
    try:
        await client.run_until_disconnected()
    finally:
        backfill_task.cancel()


async def _listen_for_backfill(app, channel_id: int, client):
    """Fulfill on-demand "pull older history" requests from the CRM for this
    channel, reusing the already-connected `client` — never opens a second
    MTProto connection on the same session (see telegram_personal_backfill's
    module docstring for why that matters: a second connection can silently
    stop this listener from receiving new messages)."""
    import json

    import redis.asyncio as redis_asyncio

    from app.models.conversation import Conversation
    from app.models.messaging_channel import MessagingChannel
    from app.services.messaging import events, telegram_personal_backfill

    with app.app_context():
        redis_url = app.config['REDIS_URL']

    r = redis_asyncio.from_url(redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(events.BACKFILL_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message['type'] != 'message':
                continue
            try:
                data = json.loads(message['data'])
            except (TypeError, ValueError):
                continue
            if data.get('channel_id') != channel_id:
                continue
            conversation_id = data.get('conversation_id')
            days = data.get('days') or 7
            with app.app_context():
                channel = MessagingChannel.query.get(channel_id)
                conv = Conversation.query.get(conversation_id) if conversation_id else None
                if not channel or not conv or conv.channel_id != channel_id:
                    continue
                try:
                    imported = await telegram_personal_backfill.backfill_conversation(client, conv, days)
                    logger.info('Channel #%s: backfilled %s messages for conversation #%s (%sd)',
                               channel_id, imported, conversation_id, days)
                    events.publish('backfill_done', channel_id, conversation_id, imported=imported)
                except Exception as exc:  # noqa: BLE001
                    logger.exception('Channel #%s: backfill failed for conversation #%s',
                                     channel_id, conversation_id)
                    events.publish('backfill_error', channel_id, conversation_id, error=str(exc))
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(events.BACKFILL_CHANNEL)
        await r.aclose()


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
