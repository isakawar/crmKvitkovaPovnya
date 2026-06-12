from datetime import datetime
from flask import render_template, request, jsonify, redirect, url_for, abort
from flask_login import login_required, current_user

from app.blueprints.notifications import notifications_bp
from app.models.user import User
from app.services.action_item_service import (
    create_action_item,
    complete_action_item,
    list_all_for_admin,
    delete_action_item,
)
from app.services.notification_service import get_notifications_for_user


def _require_admin():
    if not (getattr(current_user, 'user_type', None) == 'admin' or current_user.has_role('admin')):
        abort(403)


@notifications_bp.route('/notifications/pending')
@login_required
def pending_api():
    if getattr(current_user, 'user_type', None) == 'florist':
        return jsonify({'count': 0, 'items': []})

    items = get_notifications_for_user(current_user.id)
    return jsonify({'count': len(items), 'items': items})


@notifications_bp.route('/notifications/')
@login_required
def index():
    _require_admin()
    items = list_all_for_admin()
    managers = User.query.filter(
        User.user_type.in_(['admin', 'manager']),
        User.is_active.is_(True),
    ).order_by(User.username).all()
    return render_template('notifications/index.html', items=items, managers=managers, now=datetime.utcnow())


@notifications_bp.route('/notifications/create', methods=['POST'])
@login_required
def create():
    _require_admin()
    title = (request.form.get('title') or '').strip()
    if not title:
        return redirect(url_for('notifications.index'))

    description = (request.form.get('description') or '').strip()
    due_at_str = (request.form.get('due_at') or '').strip()
    completion_mode = request.form.get('completion_mode', 'all')
    if completion_mode not in ('any', 'all'):
        completion_mode = 'all'

    due_at = None
    if due_at_str:
        try:
            due_at = datetime.fromisoformat(due_at_str)
        except ValueError:
            pass

    user_ids_raw = request.form.getlist('user_ids')
    user_ids = []
    for uid in user_ids_raw:
        try:
            user_ids.append(int(uid))
        except (ValueError, TypeError):
            pass

    if not user_ids:
        return redirect(url_for('notifications.index'))

    create_action_item(current_user, title, description, due_at, completion_mode, user_ids)
    return redirect(url_for('notifications.index'))


@notifications_bp.route('/notifications/<int:item_id>/complete', methods=['POST'])
@login_required
def complete(item_id):
    if getattr(current_user, 'user_type', None) == 'florist':
        return jsonify({'success': False, 'error': 'Forbidden'}), 403

    success, error = complete_action_item(item_id, current_user)
    if success:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': error}), 400


@notifications_bp.route('/notifications/<int:item_id>/delete', methods=['POST'])
@login_required
def delete(item_id):
    _require_admin()
    delete_action_item(item_id)
    return jsonify({'success': True})
