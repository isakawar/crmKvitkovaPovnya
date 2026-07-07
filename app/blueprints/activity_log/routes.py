from flask import render_template, request, abort
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from app.blueprints.activity_log import activity_log_bp
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.models.client import Client
from app.models.order import Order

ENTITY_LABELS = {
    'order': 'Замовлення',
    'client': 'Клієнт',
    'subscription': 'Підписка',
    'route': 'Маршрут',
    'delivery': 'Доставка',
}

ACTION_LABELS = {
    'create': 'Створення',
    'edit': 'Редагування',
    'delete': 'Видалення',
    'extend': 'Продовження',
    'send': 'Відправка',
    'status_change': 'Зміна статусу',
    'stop': 'Зупинка',
    'resume': 'Відновлення',
}

TAB_ENTITY_MAP = {
    'orders': 'order',
    'routes': 'route',
    'subscriptions': 'subscription',
    'clients': 'client',
    'deliveries': 'delivery',
}


@activity_log_bp.route('/activity-log')
@login_required
def activity_log_list():
    if not (current_user.user_type == 'admin' or current_user.has_role('admin')):
        abort(403)

    page = int(request.args.get('page', 1))
    per_page = 50

    tab = request.args.get('tab', '').strip()
    active_tab = tab if tab in TAB_ENTITY_MAP else 'all'

    user_id = request.args.get('user_id', '').strip()
    entity_type = request.args.get('entity_type', '').strip()
    action = request.args.get('action', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    client_id = request.args.get('client_id', '').strip()
    order_id = request.args.get('order_id', '').strip()

    # Tab overrides entity_type filter (unless client/order-specific filters are active)
    if active_tab != 'all' and not client_id and not order_id:
        entity_type = TAB_ENTITY_MAP[active_tab]

    query = ActivityLog.query

    if user_id:
        query = query.filter(ActivityLog.user_id == int(user_id))

    if client_id:
        cid = int(client_id)
        order_ids = [r[0] for r in Order.query.filter_by(client_id=cid).with_entities(Order.id).all()]
        query = query.filter(or_(
            and_(ActivityLog.entity_type == 'client', ActivityLog.entity_id == cid),
            and_(ActivityLog.entity_type == 'order', ActivityLog.entity_id.in_(order_ids)),
        ))
    elif order_id:
        query = query.filter(
            ActivityLog.entity_type == 'order',
            ActivityLog.entity_id == int(order_id),
        )
    elif entity_type:
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

    # Build client lookup map for all entries that have client_id in snapshot
    client_ids = set()
    for entry in pagination.items:
        snap = entry.after_data or entry.before_data
        if snap and snap.get('client_id'):
            client_ids.add(snap['client_id'])
    clients_map = {}
    if client_ids:
        clients_map = {c.id: c for c in Client.query.filter(Client.id.in_(client_ids)).all()}

    selected_client_display = ''
    if client_id:
        c = Client.query.get(int(client_id))
        if c:
            selected_client_display = c.display_name

    return render_template(
        'activity_log/index.html',
        entries=pagination.items,
        pagination=pagination,
        users=users,
        clients_map=clients_map,
        entity_labels=ENTITY_LABELS,
        action_labels=ACTION_LABELS,
        tab_entity_map=TAB_ENTITY_MAP,
        active_tab=active_tab,
        selected_user_id=user_id,
        selected_entity_type=entity_type,
        selected_action=action,
        date_from=date_from,
        date_to=date_to,
        selected_client_id=client_id,
        selected_client_display=selected_client_display,
        selected_order_id=order_id,
    )
