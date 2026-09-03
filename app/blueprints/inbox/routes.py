import os
import uuid

from flask import (abort, current_app, jsonify, render_template, request,
                   send_from_directory)
from flask_login import current_user, login_required

from app.blueprints.inbox import inbox_bp
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.messaging_channel import MessagingChannel
from app.services.messaging import inbox_service
from app.services.messaging.adapter import get_adapter


def _require_manager():
    if not inbox_service.user_is_manager(current_user):
        abort(403)


def _conversation_or_404(conversation_id: int) -> Conversation:
    conv = Conversation.query.get_or_404(conversation_id)
    if not inbox_service.user_can_access(current_user, conv):
        abort(403)
    return conv


# --- UI ---------------------------------------------------------------
@inbox_bp.route('/inbox')
@login_required
def index():
    _require_manager()
    channel_ids = set(inbox_service.accessible_channel_ids(current_user))
    channels = [c for c in MessagingChannel.query.order_by(MessagingChannel.name).all()
                if c.id in channel_ids]
    return render_template('inbox/index.html', channels=channels)


@inbox_bp.route('/inbox/conversations')
@login_required
def conversations():
    _require_manager()
    status = request.args.get('status', 'open')
    convs = inbox_service.list_conversations(current_user, status=status)
    return jsonify({
        'conversations': [inbox_service.serialize_conversation(c) for c in convs],
        'total_unread': inbox_service.total_unread(current_user),
    })


@inbox_bp.route('/inbox/conversations/<int:conversation_id>/messages')
@login_required
def messages(conversation_id):
    _require_manager()
    conv = _conversation_or_404(conversation_id)
    after_id = request.args.get('after', type=int)
    if not after_id:
        inbox_service.mark_read(conv)
    msgs = inbox_service.get_thread(conv, after_id=after_id)
    return jsonify({
        'conversation': inbox_service.serialize_conversation(conv),
        'messages': [inbox_service.serialize_message(m) for m in msgs],
    })


@inbox_bp.route('/inbox/conversations/<int:conversation_id>/reply', methods=['POST'])
@login_required
def reply(conversation_id):
    _require_manager()
    conv = _conversation_or_404(conversation_id)
    text = (request.form.get('text') or '').strip()
    upload = request.files.get('file')

    file_path = None
    if upload and upload.filename:
        ext = upload.filename.rsplit('.', 1)[-1].lower() if '.' in upload.filename else ''
        if ext not in current_app.config.get('ALLOWED_PHOTO_EXTENSIONS', set()):
            return jsonify({'ok': False, 'error': 'Недозволений формат файлу'}), 400
        folder = current_app.config['INBOX_MEDIA_FOLDER']
        os.makedirs(folder, exist_ok=True)
        file_path = os.path.join(folder, f'{uuid.uuid4().hex}.{ext}')
        upload.save(file_path)

    if not text and not file_path:
        return jsonify({'ok': False, 'error': 'Порожнє повідомлення'}), 400

    msg = inbox_service.send_reply(conv, current_user._get_current_object(),
                                   text or None, file_path=file_path)
    ok = msg.status == 'sent'
    return jsonify({
        'ok': ok,
        'error': msg.error if not ok else None,
        'message': inbox_service.serialize_message(msg),
    }), (200 if ok else 502)


@inbox_bp.route('/inbox/conversations/<int:conversation_id>/read', methods=['POST'])
@login_required
def mark_read(conversation_id):
    _require_manager()
    conv = _conversation_or_404(conversation_id)
    inbox_service.mark_read(conv)
    return jsonify({'ok': True})


@inbox_bp.route('/inbox/conversations/<int:conversation_id>/assign', methods=['POST'])
@login_required
def assign(conversation_id):
    _require_manager()
    conv = _conversation_or_404(conversation_id)
    inbox_service.assign(conv, current_user._get_current_object())
    return jsonify({'ok': True})


@inbox_bp.route('/inbox/conversations/<int:conversation_id>/close', methods=['POST'])
@login_required
def close_conversation(conversation_id):
    _require_manager()
    inbox_service.set_status(_conversation_or_404(conversation_id), 'closed')
    return jsonify({'ok': True})


@inbox_bp.route('/inbox/conversations/<int:conversation_id>/reopen', methods=['POST'])
@login_required
def reopen_conversation(conversation_id):
    _require_manager()
    inbox_service.set_status(_conversation_or_404(conversation_id), 'open')
    return jsonify({'ok': True})


@inbox_bp.route('/inbox/media/<int:message_id>/<int:idx>')
@login_required
def media(message_id, idx):
    _require_manager()
    msg = Message.query.get_or_404(message_id)
    if not inbox_service.user_can_access(current_user, msg.conversation):
        abort(403)
    stored = inbox_service.ensure_media_downloaded(msg, idx)
    if not stored:
        abort(404)
    return send_from_directory(current_app.config['INBOX_MEDIA_FOLDER'], stored)


# --- inbound webhook (public) ---------------------------------------
@inbox_bp.route('/api/messaging/telegram/<int:channel_id>/webhook', methods=['POST'])
def telegram_webhook(channel_id):
    channel = MessagingChannel.query.get(channel_id)
    if channel is None:
        abort(404)
    adapter = get_adapter(channel)
    if not adapter.verify_webhook(request.headers, channel):
        abort(401)

    payload = request.get_json(silent=True) or {}
    try:
        events = adapter.parse_events(payload)
    except Exception:  # noqa: BLE001
        current_app.logger.exception('inbox webhook: parse_events failed')
        return '', 200

    for event in events:
        msg = inbox_service.ingest_event(channel, event)
        if msg is not None and event.kind == 'message' and event.media:
            inbox_service.prefetch_message_media(current_app._get_current_object(), msg.id)
    return '', 200
