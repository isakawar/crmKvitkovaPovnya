import os
from datetime import datetime, timedelta

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.messaging_channel import MessagingChannel
from app.services.messaging.media_cleanup import purge_old_media


def _conv(session):
    ch = MessagingChannel(name='TG', channel_type='telegram', webhook_secret='x', external_id='BC1')
    session.add(ch)
    session.commit()
    conv = Conversation(channel_id=ch.id, external_chat_id='1')
    session.add(conv)
    session.commit()
    return conv


def test_purge_deletes_old_files_keeps_recent(app, session, tmp_path):
    app.config['INBOX_MEDIA_FOLDER'] = str(tmp_path)
    conv = _conv(session)

    old_file = tmp_path / 'old.jpg'
    old_file.write_bytes(b'x')
    recent_file = tmp_path / 'recent.jpg'
    recent_file.write_bytes(b'x')

    old_msg = Message(
        conversation_id=conv.id, direction='in', text=None,
        media=[{'type': 'photo', 'path': 'old.jpg', 'mime': 'image/jpeg'}],
        tg_date=datetime.utcnow() - timedelta(days=30),
    )
    recent_msg = Message(
        conversation_id=conv.id, direction='in', text=None,
        media=[{'type': 'photo', 'path': 'recent.jpg', 'mime': 'image/jpeg'}],
        tg_date=datetime.utcnow() - timedelta(days=1),
    )
    session.add_all([old_msg, recent_msg])
    session.commit()

    result = purge_old_media(days=14)

    assert result['files_deleted'] == 1
    assert result['messages_touched'] == 1
    assert not os.path.exists(old_file)
    assert os.path.exists(recent_file)

    session.refresh(old_msg)
    session.refresh(recent_msg)
    assert old_msg.media[0]['expired'] is True
    assert old_msg.media[0]['path'] is None
    assert recent_msg.media[0].get('expired', False) is False


def test_purge_is_idempotent_on_already_expired(app, session, tmp_path):
    app.config['INBOX_MEDIA_FOLDER'] = str(tmp_path)
    conv = _conv(session)
    msg = Message(
        conversation_id=conv.id, direction='in', text=None,
        media=[{'type': 'photo', 'path': None, 'mime': 'image/jpeg', 'expired': True}],
        tg_date=datetime.utcnow() - timedelta(days=30),
    )
    session.add(msg)
    session.commit()

    result = purge_old_media(days=14)
    assert result['files_deleted'] == 0
    assert result['messages_touched'] == 0
