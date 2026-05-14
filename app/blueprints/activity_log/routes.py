from flask import render_template, request, abort
from flask_login import login_required, current_user
from app.blueprints.activity_log import activity_log_bp
from app.models.activity_log import ActivityLog
from app.models.user import User

ENTITY_LABELS = {
    'order': 'Замовлення',
    'client': 'Клієнт',
    'subscription': 'Підписка',
}

ACTION_LABELS = {
    'create': 'Створення',
    'edit': 'Редагування',
    'delete': 'Видалення',
    'extend': 'Продовження',
}


@activity_log_bp.route('/activity-log')
@login_required
def activity_log_list():
    if not (current_user.user_type == 'admin' or current_user.has_role('admin')):
        abort(403)

    page = int(request.args.get('page', 1))
    per_page = 50

    user_id = request.args.get('user_id', '').strip()
    entity_type = request.args.get('entity_type', '').strip()
    action = request.args.get('action', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    query = ActivityLog.query

    if user_id:
        query = query.filter(ActivityLog.user_id == int(user_id))
    if entity_type:
        query = query.filter(ActivityLog.entity_type == entity_type)
    if action:
        query = query.filter(ActivityLog.action == action)
    if date_from:
        from datetime import datetime
        try:
            query = query.filter(ActivityLog.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        from datetime import datetime, timedelta
        try:
            query = query.filter(ActivityLog.created_at < datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
        except ValueError:
            pass

    pagination = query.order_by(ActivityLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    users = User.query.filter(User.user_type.in_(['admin', 'manager'])).order_by(User.display_name).all()

    return render_template(
        'activity_log/index.html',
        entries=pagination.items,
        pagination=pagination,
        users=users,
        entity_labels=ENTITY_LABELS,
        action_labels=ACTION_LABELS,
        selected_user_id=user_id,
        selected_entity_type=entity_type,
        selected_action=action,
        date_from=date_from,
        date_to=date_to,
    )
