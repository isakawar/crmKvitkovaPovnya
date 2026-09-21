import json
import os
import uuid

import redis as redis_lib
from flask import (Response, abort, current_app, jsonify, render_template,
                   request, send_from_directory, stream_with_context)
from flask_login import current_user, login_required

from app.blueprints.inbox import inbox_bp
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.messaging_channel import MessagingChannel
from app.services import client_service
from app.services.messaging import inbox_service
from app.services.messaging.adapter import get_adapter
from app.services.messaging.events import CHANNEL as INBOX_EVENTS_CHANNEL


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
    channel_ids = inbox_service.accessible_channel_ids(current_user)
    channels = (MessagingChannel.query
                .filter(MessagingChannel.id.in_(channel_ids))
                .order_by(MessagingChannel.name).all()) if channel_ids else []
    personal_channels = [c for c in channels if c.channel_type == 'telegram_personal' and c.is_connected]
    return render_template('inbox/index.html', channels=channels, personal_channels=personal_channels)


@inbox_bp.route('/inbox/conversations')
@login_required
def conversations():
    _require_manager()
    unread_only = request.args.get('filter') == 'unread'
    channel_ids = inbox_service.accessible_channel_ids(current_user)
    convs = inbox_service.list_conversations(current_user, unread_only=unread_only, channel_ids=channel_ids)
    return jsonify({
        'conversations': [inbox_service.serialize_conversation(c) for c in convs],
        'total_unread': inbox_service.total_unread(current_user, channel_ids=channel_ids),
    })


@inbox_bp.route('/inbox/stream')
@login_required
def stream():
    """SSE feed: pushes a tiny 'a message changed' ping so the UI can refetch
    instantly instead of waiting for its next poll. Carries no message
    content itself — the client re-fetches via the existing JSON endpoints,
    which keeps this stream generic across every channel/event kind and
    re-checks access on every payload it emits.
    """
    _require_manager()
    allowed = set(inbox_service.accessible_channel_ids(current_user._get_current_object()))
    redis_url = current_app.config['REDIS_URL']

    def gen():
        r = redis_lib.from_url(redis_url)
        pubsub = r.pubsub()
        pubsub.subscribe(INBOX_EVENTS_CHANNEL)
        try:
            yield ': connected\n\n'
            while True:
                msg = pubsub.get_message(timeout=15)
                if msg is None or msg.get('type') != 'message':
                    yield ': ping\n\n'
                    continue
                try:
                    data = json.loads(msg['data'])
                except (TypeError, ValueError):
                    continue
                if data.get('channel_id') in allowed:
                    yield 'data: ' + json.dumps(data) + '\n\n'
        finally:
            pubsub.close()

    return Response(stream_with_context(gen()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@inbox_bp.route('/inbox/conversations/new', methods=['POST'])
@login_required
def new_conversation():
    _require_manager()
    data = request.get_json(silent=True) or {}
    channel_id = data.get('channel_id')
    query = (data.get('query') or '').strip()
    if not channel_id or not query:
        return jsonify({'ok': False, 'error': 'Вкажіть канал і номер/username'}), 400

    channel = MessagingChannel.query.get_or_404(channel_id)
    if not inbox_service.user_can_access(current_user, channel):
        abort(403)
    try:
        conv = inbox_service.start_conversation(channel, query)
        return jsonify({'ok': True, 'conversation': inbox_service.serialize_conversation(conv)})
    except Exception as exc:  # noqa: BLE001
        return jsonify({'ok': False, 'error': str(exc)}), 400


@inbox_bp.route('/inbox/conversations/<int:conversation_id>/messages')
@login_required
def messages(conversation_id):
    _require_manager()
    conv = _conversation_or_404(conversation_id)
    after_id = request.args.get('after', type=int)
    before_id = request.args.get('before', type=int)
    if not after_id and not before_id:
        inbox_service.mark_read(conv)
    msgs, has_more = inbox_service.get_thread(conv, after_id=after_id, before_id=before_id)
    return jsonify({
        'conversation': inbox_service.serialize_conversation(conv),
        'messages': [inbox_service.serialize_message(m, channel_type=conv.channel.channel_type) for m in msgs],
        'has_more': has_more,
    })


@inbox_bp.route('/inbox/conversations/<int:conversation_id>/client-panel')
@login_required
def client_panel(conversation_id):
    _require_manager()
    conv = _conversation_or_404(conversation_id)
    return jsonify(inbox_service.get_client_panel(conv))


@inbox_bp.route('/inbox/conversations/<int:conversation_id>/link-client', methods=['POST'])
@login_required
def link_client(conversation_id):
    _require_manager()
    conv = _conversation_or_404(conversation_id)
    data = request.get_json(silent=True) or {}
    client_id = data.get('client_id')
    client = inbox_service.link_client(conv, client_id) if client_id else None
    if not client:
        return jsonify({'ok': False, 'error': 'Клієнта не знайдено'}), 400
    return jsonify({'ok': True, 'panel': inbox_service.get_client_panel(conv)})


@inbox_bp.route('/inbox/conversations/<int:conversation_id>/unlink-client', methods=['POST'])
@login_required
def unlink_client(conversation_id):
    _require_manager()
    conv = _conversation_or_404(conversation_id)
    inbox_service.unlink_client(conv)
    return jsonify({'ok': True})


@inbox_bp.route('/inbox/clients/search')
@login_required
def search_clients_for_link():
    _require_manager()
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'clients': []})
    pagination = client_service.search_clients(q=q, page=1, per_page=8)
    return jsonify({'clients': [
        {'id': c.id, 'name': c.display_name, 'phone': c.phone or '',
         'instagram': c.instagram or '', 'telegram': c.telegram or ''}
        for c in pagination.items
    ]})


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
        'message': inbox_service.serialize_message(msg, channel_type=conv.channel.channel_type),
    }), (200 if ok else 502)


@inbox_bp.route('/inbox/conversations/<int:conversation_id>/read', methods=['POST'])
@login_required
def mark_read(conversation_id):
    _require_manager()
    conv = _conversation_or_404(conversation_id)
    inbox_service.mark_read(conv)
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
    # Stored under a random uuid filename and never overwritten in place, so
    # it's safe to let the browser cache it hard and skip refetching on
    # every scroll/reopen — only revalidated via ETag when the tab is fresh.
    return send_from_directory(current_app.config['INBOX_MEDIA_FOLDER'], stored,
                               max_age=2592000, conditional=True)


# --- inbound webhooks (public) -------------------------------------
def _handle_webhook(channel):
    adapter = get_adapter(channel)

    if request.method == 'GET':
        challenge = adapter.verify_subscription(request.args, channel)
        if challenge is None:
            abort(403)
        return challenge, 200

    if not adapter.verify_webhook(request, channel):
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


@inbox_bp.route('/api/messaging/telegram/<int:channel_id>/webhook', methods=['POST'])
def telegram_webhook(channel_id):
    channel = MessagingChannel.query.get(channel_id)
    if channel is None or channel.channel_type != 'telegram':
        abort(404)
    return _handle_webhook(channel)


@inbox_bp.route('/api/messaging/instagram/<int:channel_id>/webhook', methods=['GET', 'POST'])
def instagram_webhook(channel_id):
    channel = MessagingChannel.query.get(channel_id)
    if channel is None or channel.channel_type != 'instagram':
        abort(404)
    return _handle_webhook(channel)


@inbox_bp.route('/api/messaging/viber/<int:channel_id>/webhook', methods=['POST'])
def viber_webhook(channel_id):
    channel = MessagingChannel.query.get(channel_id)
    if channel is None or channel.channel_type != 'viber':
        abort(404)
    return _handle_webhook(channel)


@inbox_bp.route('/api/messaging/whatsapp/<int:channel_id>/webhook', methods=['GET', 'POST'])
def whatsapp_webhook(channel_id):
    channel = MessagingChannel.query.get(channel_id)
    if channel is None or channel.channel_type != 'whatsapp':
        abort(404)
    return _handle_webhook(channel)
