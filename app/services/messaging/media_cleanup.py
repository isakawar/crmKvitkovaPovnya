"""Delete old inbox media files from disk to bound long-term storage growth.

Message rows (text history) are never touched — only the downloaded file on
disk is removed, and the media entry is marked `expired` so nothing tries to
re-download it afterwards (see `ensure_media_downloaded`'s early-out).
Channel-agnostic: applies to telegram, telegram_personal and instagram alike.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy.orm.attributes import flag_modified

from app.extensions import db
from app.models.message import Message

log = logging.getLogger(__name__)


def purge_old_media(days: int = 14) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)
    folder = current_app.config['INBOX_MEDIA_FOLDER']

    # `media` is a plain Postgres `json` column (no <> operator) — filter by
    # date in SQL, then skip text-only rows in Python.
    candidates = (
        Message.query
        .filter(db.func.coalesce(Message.tg_date, Message.created_at) < cutoff)
        .all()
    )

    messages_touched = 0
    files_deleted = 0

    for msg in candidates:
        if not msg.media:
            continue
        media = [dict(m) for m in msg.media]  # fresh dicts, not shared with msg.media's
        changed = False
        for item in media:
            path = item.get('path')
            if not path:
                continue  # never downloaded — no disk space used, leave it lazily fetchable
            try:
                os.remove(os.path.join(folder, path))
                files_deleted += 1
            except FileNotFoundError:
                pass
            except OSError:
                log.exception('failed to delete media file %s (message %s)', path, msg.id)
            item['path'] = None
            item['expired'] = True
            changed = True
        if changed:
            msg.media = media
            flag_modified(msg, 'media')
            messages_touched += 1

    if messages_touched:
        db.session.commit()

    return {'messages_touched': messages_touched, 'files_deleted': files_deleted}
