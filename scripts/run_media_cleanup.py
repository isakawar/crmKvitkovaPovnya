#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Daily loop: delete inbox media older than N days (default 14) from disk.

Runs once at startup, then every 24h. Text history is never touched — see
app/services/messaging/media_cleanup.py.
"""
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

DAYS = int(os.environ.get('INBOX_MEDIA_RETENTION_DAYS', 14))
INTERVAL_SECONDS = 24 * 60 * 60


def wait_for_database():
    max_retries = 30
    for attempt in range(1, max_retries + 1):
        try:
            app = create_app()
            with app.app_context():
                from app.extensions import db
                with db.engine.connect() as conn:
                    conn.execute(db.text('SELECT 1'))
                return app
        except Exception as exc:
            logger.warning('Database not ready (attempt %s/%s): %s', attempt, max_retries, exc)
            time.sleep(2)
    raise RuntimeError('Could not connect to database after maximum retries')


def main():
    logger.info('=== MEDIA CLEANUP (retention: %s days) ===', DAYS)
    app = wait_for_database()
    from app.services.messaging.media_cleanup import purge_old_media

    while True:
        try:
            with app.app_context():
                result = purge_old_media(days=DAYS)
                logger.info('Purged %s files (%s messages touched)',
                            result['files_deleted'], result['messages_touched'])
        except Exception:
            logger.exception('Cleanup run failed')
        time.sleep(INTERVAL_SECONDS)


if __name__ == '__main__':
    main()
