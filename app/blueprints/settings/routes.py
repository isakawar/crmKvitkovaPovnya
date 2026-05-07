from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import Settings, Price
from app.models.price_preset import PricePreset
from app.models.courier import Courier
from app.models.user import User, Role, ROLE_PERMISSIONS
from app.models.expense_category import ExpenseCategory
from app.extensions import db
from app.utils.decorators import permission_required

bp = Blueprint('settings', __name__)

@bp.route('/settings')
@login_required
@permission_required('view_settings')
def settings_page():
    return render_template('settings/index.html')


@bp.route('/settings/couriers')
@login_required
@permission_required('view_settings')
def couriers_page():
    couriers = Courier.query.order_by(Courier.name).all()
    active_couriers = [c for c in couriers if c.active]
    telegram_couriers = [c for c in couriers if c.telegram_registered]
    courier_stats = {
        'total': len(couriers),
        'active': len(active_couriers),
        'telegram': len(telegram_couriers),
    }
    return render_template(
        'settings/couriers.html',
        couriers=couriers,
        courier_stats=courier_stats
    )


@bp.route('/settings/users')
@login_required
@permission_required('manage_users')
def users_page():
    return render_template('settings/users.html')


@bp.route('/settings/directories')
@login_required
@permission_required('view_settings')
def directories_page():
    return render_template('settings/directories.html')


@bp.route('/settings/features')
@login_required
@permission_required('edit_settings')
def features_page():
    return render_template('settings/features.html')


@bp.route('/settings/charges')
@login_required
@permission_required('view_settings')
def charges_page():
    from app.services.billing_service import get_charges_data
    date_from = request.args.get('date_from', '').strip() or None
    date_to = request.args.get('date_to', '').strip() or None
    data = get_charges_data(date_from, date_to)
    return render_template(
        'settings/charges.html',
        rows=data['rows'],
        total_amount=data['total_amount'],
        count=data['count'],
        date_from=date_from or '',
        date_to=date_to or '',
    )

@bp.route('/settings/update', methods=['POST'])
@login_required
@permission_required('edit_settings')
def update_settings():
    settings = Settings.query.first()
    if not settings:
        settings = Settings()
        db.session.add(settings)
    
    settings.pickup_time_start = request.form.get('pickup_time_start')
    settings.pickup_time_end = request.form.get('pickup_time_end')
    settings.delivery_time_start = request.form.get('delivery_time_start')
    settings.delivery_time_end = request.form.get('delivery_time_end')
    
    db.session.commit()
    
    return jsonify({'status': 'success'})

@bp.route('/settings/delivery_types', methods=['GET'])
def get_delivery_types():
    items = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])

@bp.route('/settings/delivery_types', methods=['POST'])
def add_delivery_type():
    data = request.get_json()
    value = (data.get('value') or '').strip()
    if not value:
        return jsonify({'success': False, 'error': 'Назва не може бути порожньою'}), 400
    if Settings.query.filter_by(type='delivery_type', value=value).first():
        return jsonify({'success': False, 'error': 'Такий тип вже існує'}), 400
    item = Settings(type='delivery_type', value=value)
    db.session.add(item)
    db.session.commit()
    return jsonify({'success': True, 'item': {'id': item.id, 'value': item.value}})

@bp.route('/settings/sizes', methods=['GET'])
def get_sizes():
    items = Settings.query.filter_by(type='size').order_by(Settings.sort_order.nullslast(), Settings.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])

@bp.route('/settings/sizes', methods=['POST'])
def add_size():
    data = request.get_json()
    value = (data.get('value') or '').strip()
    if not value:
        return jsonify({'success': False, 'error': 'Назва не може бути порожньою'}), 400
    if Settings.query.filter_by(type='size', value=value).first():
        return jsonify({'success': False, 'error': 'Такий розмір вже існує'}), 400
    max_order = db.session.query(db.func.max(Settings.sort_order)).filter_by(type='size').scalar() or 0
    item = Settings(type='size', value=value, sort_order=max_order + 1)
    db.session.add(item)
    db.session.commit()
    return jsonify({'success': True, 'item': {'id': item.id, 'value': item.value}})

@bp.route('/settings/for_whom', methods=['GET'])
def get_for_whom():
    items = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])

@bp.route('/settings/for_whom', methods=['POST'])
def add_for_whom():
    data = request.get_json()
    value = (data.get('value') or '').strip()
    if not value:
        return jsonify({'success': False, 'error': 'Назва не може бути порожньою'}), 400
    if Settings.query.filter_by(type='for_whom', value=value).first():
        return jsonify({'success': False, 'error': 'Такий варіант вже існує'}), 400
    item = Settings(type='for_whom', value=value)
    db.session.add(item)
    db.session.commit()
    return jsonify({'success': True, 'item': {'id': item.id, 'value': item.value}})

@bp.route('/settings/marketing_sources', methods=['GET'])
def get_marketing_sources():
    items = Settings.query.filter_by(type='marketing_source').order_by(Settings.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])

@bp.route('/settings/marketing_sources', methods=['POST'])
def add_marketing_source():
    data = request.get_json()
    value = (data.get('value') or '').strip()
    if not value:
        return jsonify({'success': False, 'error': 'Назва не може бути порожньою'}), 400
    if Settings.query.filter_by(type='marketing_source', value=value).first():
        return jsonify({'success': False, 'error': 'Такий варіант вже існує'}), 400
    item = Settings(type='marketing_source', value=value)
    db.session.add(item)
    db.session.commit()
    return jsonify({'success': True, 'item': {'id': item.id, 'value': item.value}})


@bp.route('/settings/packaging_types', methods=['GET'])
def get_packaging_types():
    items = Settings.query.filter_by(type='packaging_type').order_by(Settings.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])

@bp.route('/settings/packaging_types', methods=['POST'])
def add_packaging_type():
    data = request.get_json()
    value = (data.get('value') or '').strip()
    if not value:
        return jsonify({'success': False, 'error': 'Назва не може бути порожньою'}), 400
    if Settings.query.filter_by(type='packaging_type', value=value).first():
        return jsonify({'success': False, 'error': 'Такий тип вже існує'}), 400
    item = Settings(type='packaging_type', value=value)
    db.session.add(item)
    db.session.commit()
    return jsonify({'success': True, 'item': {'id': item.id, 'value': item.value}})


@bp.route('/settings/expense_categories', methods=['GET'])
@login_required
@permission_required('view_settings')
def get_expense_categories():
    from sqlalchemy import func
    rows = (
        db.session.query(
            ExpenseCategory,
            func.count(Settings.id).label('expense_types_count'),
        )
        .outerjoin(Settings, (Settings.category_id == ExpenseCategory.id) & (Settings.type == 'expense_type'))
        .group_by(ExpenseCategory.id)
        .order_by(ExpenseCategory.name)
        .all()
    )
    return jsonify([{
        'id': cat.id,
        'name': cat.name,
        'slug': cat.slug,
        'expense_types_count': count,
    } for cat, count in rows])


@bp.route('/settings/expense_categories', methods=['POST'])
@login_required
@permission_required('edit_settings')
def add_expense_category():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    slug = (data.get('slug') or '').strip()
    errors = []
    if not name:
        errors.append('Назва не може бути порожньою')
    if not slug:
        errors.append('Slug не може бути порожнім')
    if slug and not slug.replace('_', '').replace('-', '').isalnum():
        errors.append('Slug може містити лише латинські літери, цифри, дефіс і підкреслення')
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400
    if ExpenseCategory.query.filter_by(name=name).first():
        return jsonify({'success': False, 'error': 'Категорія з такою назвою вже існує'}), 400
    if ExpenseCategory.query.filter_by(slug=slug).first():
        return jsonify({'success': False, 'error': 'Категорія з таким slug вже існує'}), 400
    cat = ExpenseCategory(name=name, slug=slug)
    db.session.add(cat)
    db.session.commit()
    return jsonify({'success': True, 'category': {'id': cat.id, 'name': cat.name, 'slug': cat.slug, 'expense_types_count': 0}})


@bp.route('/settings/expense_categories/<int:cat_id>', methods=['DELETE'])
@login_required
@permission_required('edit_settings')
def delete_expense_category(cat_id):
    cat = ExpenseCategory.query.get_or_404(cat_id)
    in_use = Settings.query.filter_by(type='expense_type', category_id=cat_id).first()
    if in_use:
        return jsonify({'success': False, 'error': 'Категорія використовується і не може бути видалена'}), 400
    db.session.delete(cat)
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/settings/<int:item_id>/category', methods=['PATCH'])
@login_required
@permission_required('edit_settings')
def update_expense_type_category(item_id):
    item = Settings.query.get_or_404(item_id)
    if item.type != 'expense_type':
        return jsonify({'success': False, 'error': 'Not an expense type'}), 400
    data = request.get_json()
    category_id = data.get('category_id')
    item.category_id = int(category_id) if category_id else None
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/settings/expense_types', methods=['GET'])
def get_expense_types():
    items = Settings.query.filter_by(type='expense_type').order_by(Settings.value).all()
    return jsonify([{
        'id': i.id,
        'value': i.value,
        'category_id': i.category_id,
        'category_slug': i.category.slug if i.category else None,
        'category_name': i.category.name if i.category else None,
    } for i in items])

@bp.route('/settings/expense_types', methods=['POST'])
@login_required
@permission_required('edit_settings')
def add_expense_type():
    data = request.get_json()
    value = (data.get('value') or '').strip()
    if not value:
        return jsonify({'success': False, 'error': 'Назва не може бути порожньою'}), 400
    if Settings.query.filter_by(type='expense_type', value=value).first():
        return jsonify({'success': False, 'error': 'Такий тип вже існує'}), 400
    category_id = data.get('category_id')
    item = Settings(type='expense_type', value=value, category_id=int(category_id) if category_id else None)
    db.session.add(item)
    db.session.commit()
    return jsonify({'success': True, 'item': {
        'id': item.id, 'value': item.value,
        'category_id': item.category_id,
        'category_slug': item.category.slug if item.category else None,
        'category_name': item.category.name if item.category else None,
    }})


@bp.route('/settings/<int:item_id>', methods=['DELETE'])
@login_required
@permission_required('edit_settings')
def delete_setting(item_id):
    from app.models.transaction import Transaction
    item = Settings.query.get_or_404(item_id)
    if item.type == 'expense_type':
        in_use = Transaction.query.filter_by(expense_type=item.value).first()
        if in_use:
            return jsonify({'success': False, 'error': 'Тип витрати використовується в транзакціях і не може бути видалений'}), 400
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/settings/prices', methods=['GET'])
def get_prices():
    sizes = Settings.query.filter_by(type='size').order_by(Settings.sort_order.nullslast(), Settings.value).all()
    presets = PricePreset.query.order_by(PricePreset.id).all()

    # Determine which preset's prices to return
    preset_id_param = request.args.get('preset_id', type=int)
    if preset_id_param:
        target_preset = PricePreset.query.get(preset_id_param)
    else:
        target_preset = next((p for p in presets if p.is_active), presets[0] if presets else None)

    price_map = {}
    if target_preset:
        for p in Price.query.filter_by(preset_id=target_preset.id).all():
            price_map[f'{p.order_type}_{p.size_id}'] = p.price

    return jsonify({
        'presets': [{'id': p.id, 'name': p.name, 'is_active': p.is_active} for p in presets],
        'sizes': [{'id': s.id, 'value': s.value} for s in sizes if s.value.lower() != 'власний'],
        'prices': price_map,
    })


@bp.route('/settings/ai-agent/toggle', methods=['POST'])
@login_required
@permission_required('edit_settings')
def toggle_ai_agent():
    from app.models.settings import Settings
    flag = Settings.query.filter_by(type='feature_flag', value='ai_agent_disabled').first()
    if flag:
        db.session.delete(flag)
        db.session.commit()
        return jsonify({'success': True, 'enabled': True})
    else:
        db.session.add(Settings(type='feature_flag', value='ai_agent_disabled'))
        db.session.commit()
        return jsonify({'success': True, 'enabled': False})


@bp.route('/settings/distribute-banner/toggle', methods=['POST'])
@login_required
@permission_required('edit_settings')
def toggle_distribute_banner():
    from app.models.settings import Settings
    flag = Settings.query.filter_by(type='feature_flag', value='distribute_banner_disabled').first()
    if flag:
        db.session.delete(flag)
        db.session.commit()
        return jsonify({'success': True, 'enabled': True})
    else:
        db.session.add(Settings(type='feature_flag', value='distribute_banner_disabled'))
        db.session.commit()
        return jsonify({'success': True, 'enabled': False})


@bp.route('/settings/prices', methods=['POST'])
def save_prices():
    data = request.get_json()
    # data: { "preset_id": int, "prices": { "one_time_<size_id>": price, "subscription_<size_id>": price } }
    preset_id = data.get('preset_id')
    prices_data = data.get('prices', {})

    preset = PricePreset.query.get(preset_id)
    if not preset:
        return jsonify({'success': False, 'error': 'Пресет не знайдено'}), 404

    for key, value in prices_data.items():
        # key format: "one_time_<size_id>" or "subscription_<size_id>"
        if key.startswith('one_time_'):
            order_type = 'one_time'
            try:
                size_id = int(key[len('one_time_'):])
            except ValueError:
                continue
        elif key.startswith('subscription_'):
            order_type = 'subscription'
            try:
                size_id = int(key[len('subscription_'):])
            except ValueError:
                continue
        else:
            continue

        try:
            price_val = int(value)
        except (ValueError, TypeError):
            price_val = 0

        existing = Price.query.filter_by(preset_id=preset_id, order_type=order_type, size_id=size_id).first()
        if existing:
            existing.price = price_val
        else:
            db.session.add(Price(preset_id=preset_id, order_type=order_type, size_id=size_id, price=price_val))

    db.session.commit()
    return jsonify({'success': True})


@bp.route('/settings/prices/presets', methods=['POST'])
def create_price_preset():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Назва не може бути порожньою'}), 400
    copy_from_id = data.get('copy_from_id')

    preset = PricePreset(name=name, is_active=False)
    db.session.add(preset)
    db.session.flush()  # get preset.id

    if copy_from_id:
        source_prices = Price.query.filter_by(preset_id=copy_from_id).all()
        for p in source_prices:
            db.session.add(Price(preset_id=preset.id, order_type=p.order_type, size_id=p.size_id, price=p.price))

    db.session.commit()
    return jsonify({'success': True, 'preset': {'id': preset.id, 'name': preset.name, 'is_active': preset.is_active}})


@bp.route('/settings/prices/presets/<int:preset_id>/activate', methods=['POST'])
def activate_price_preset(preset_id):
    preset = PricePreset.query.get(preset_id)
    if not preset:
        return jsonify({'success': False, 'error': 'Пресет не знайдено'}), 404

    PricePreset.query.update({'is_active': False})
    preset.is_active = True
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/settings/prices/presets/<int:preset_id>', methods=['DELETE'])
def delete_price_preset(preset_id):
    preset = PricePreset.query.get(preset_id)
    if not preset:
        return jsonify({'success': False, 'error': 'Пресет не знайдено'}), 404
    if preset.is_active:
        return jsonify({'success': False, 'error': 'Не можна видалити активний пресет'}), 400

    db.session.delete(preset)
    db.session.commit()
    return jsonify({'success': True})


# ── User Management (admin only) ────────────────────────────────────────────

@bp.route('/settings/users/list', methods=['GET'])
@login_required
@permission_required('manage_users')
def get_users():
    users = User.query.order_by(User.username).all()
    result = []
    for u in users:
        role_names = [r.name for r in u.roles]
        result.append({
            'id': u.id,
            'username': u.username,
            'display_name': u.display_name or '',
            'user_type': u.user_type,
            'roles': role_names,
            'is_active': u.is_active,
            'is_online': u.is_online,
            'last_seen': u.last_seen.isoformat() if u.last_seen else None,
            'last_login': u.last_login.isoformat() if u.last_login else None,
        })
    return jsonify(result)


@bp.route('/settings/users', methods=['POST'])
@login_required
@permission_required('manage_users')
def create_user():
    data = request.get_json()
    username = (data.get('username') or '').strip()
    display_name = (data.get('display_name') or '').strip() or None
    password = data.get('password') or ''
    password_confirm = data.get('password_confirm') or ''
    role_name = (data.get('role') or '').strip()

    errors = []
    if not username:
        errors.append('Логін не може бути порожнім')
    if not password:
        errors.append('Пароль не може бути порожнім')
    elif len(password) < 6:
        errors.append('Пароль має бути не менше 6 символів')
    if password != password_confirm:
        errors.append('Паролі не збігаються')
    if role_name not in ('admin', 'manager', 'florist'):
        errors.append('Роль має бути admin, manager або florist')
    if username and User.query.filter_by(username=username).first():
        errors.append('Користувач з таким логіном вже існує')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    role = Role.query.filter_by(name=role_name).first()
    if not role:
        role = Role(name=role_name, description=role_name.capitalize())
        db.session.add(role)
        db.session.flush()

    email = f'{username}@crm.local'
    user = User(username=username, display_name=display_name, email=email, user_type=role_name, is_active=True)
    user.set_password(password)
    user.roles.append(role)
    db.session.add(user)
    db.session.commit()

    return jsonify({'success': True, 'user': {
        'id': user.id,
        'username': user.username,
        'display_name': user.display_name or '',
        'user_type': user.user_type,
        'roles': [role_name],
        'is_active': user.is_active,
    }})


@bp.route('/settings/users/<int:user_id>', methods=['PUT'])
@login_required
@permission_required('manage_users')
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    username = (data.get('username') or '').strip()
    display_name = (data.get('display_name') or '').strip() or None
    role_name = (data.get('role') or '').strip()
    password = (data.get('password') or '').strip()
    password_confirm = (data.get('password_confirm') or '').strip()

    errors = []
    if not username:
        errors.append('Логін не може бути порожнім')
    if role_name not in ('admin', 'manager', 'florist'):
        errors.append('Недійсна роль')
    if password and len(password) < 6:
        errors.append('Пароль має бути не менше 6 символів')
    if password and password != password_confirm:
        errors.append('Паролі не збігаються')
    if username and User.query.filter(User.username == username, User.id != user_id).first():
        errors.append('Користувач з таким логіном вже існує')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    user.username = username
    user.display_name = display_name
    user.user_type = role_name

    role = Role.query.filter_by(name=role_name).first()
    if not role:
        role = Role(name=role_name, description=role_name.capitalize())
        db.session.add(role)
        db.session.flush()
    user.roles = [role]

    if password:
        user.set_password(password)

    db.session.commit()
    return jsonify({'success': True, 'user': {
        'id': user.id,
        'username': user.username,
        'display_name': user.display_name or '',
        'user_type': user.user_type,
        'roles': [role_name],
        'is_active': user.is_active,
        'is_online': user.is_online,
        'last_seen': user.last_seen.isoformat() if user.last_seen else None,
        'last_login': user.last_login.isoformat() if user.last_login else None,
    }})


@bp.route('/settings/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@permission_required('manage_users')
def toggle_user_active(user_id):
    if user_id == current_user.id:
        return jsonify({'success': False, 'error': 'Не можна деактивувати себе'}), 400
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': user.is_active})


@bp.route('/settings/users/<int:user_id>/password', methods=['POST'])
@login_required
@permission_required('manage_users')
def change_user_password(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    password = data.get('password') or ''
    password_confirm = data.get('password_confirm') or ''

    if not password:
        return jsonify({'success': False, 'error': 'Пароль не може бути порожнім'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Пароль має бути не менше 6 символів'}), 400
    if password != password_confirm:
        return jsonify({'success': False, 'error': 'Паролі не збігаються'}), 400

    user.set_password(password)
    db.session.commit()
    return jsonify({'success': True})
