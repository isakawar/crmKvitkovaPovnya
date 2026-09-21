import os
import secrets
import uuid
import requests
from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app, redirect, session, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.constants import SETTING_EXPENSE_TYPE, SETTING_PAYMENT_ACCOUNT, SETTING_SIZE
from app.models import Settings, Price
from app.models.price_preset import PricePreset
from app.models.courier import Courier
from app.models.user import User, Role, ROLE_PERMISSIONS
from app.models.expense_category import ExpenseCategory
from app.extensions import db
from app.utils.decorators import permission_required
from app.services.csv_import_service import normalize_phone

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


@bp.route('/settings/messaging')
@login_required
@permission_required('edit_settings')
def messaging_page():
    from app.services.messaging import channel_config_service as ccs
    channels = ccs.list_channels()
    managers = User.query.filter(User.user_type.in_(('admin', 'manager'))).order_by(User.username).all()
    base = (current_app.config.get('CRM_PUBLIC_URL') or '').rstrip('/')
    webhooks = {c.id: (base + ccs.webhook_path(c)) if base else ccs.webhook_path(c) for c in channels}
    return render_template(
        'settings/messaging.html',
        channels=channels, managers=managers, webhooks=webhooks,
        tg_token_set=bool(current_app.config.get('INBOX_TELEGRAM_BOT_TOKEN')),
        ig_secret_set=bool(current_app.config.get('INBOX_INSTAGRAM_APP_SECRET')),
        tg_personal_creds_set=bool(current_app.config.get('MESSAGING_TG_API_ID')
                                    and current_app.config.get('MESSAGING_TG_API_HASH')
                                    and current_app.config.get('MESSAGING_SESSION_KEY')),
        viber_token_set=bool(current_app.config.get('INBOX_VIBER_BOT_TOKEN')),
        public_url_set=bool(base),
        facebook_app_id=current_app.config.get('FACEBOOK_APP_ID') or '',
        whatsapp_config_id=current_app.config.get('FACEBOOK_WHATSAPP_CONFIG_ID') or '',
        graph_version=current_app.config.get('INBOX_INSTAGRAM_GRAPH_VERSION') or 'v23.0',
        fb_error=request.args.get('fb_error'),
        fb_success=request.args.get('fb_success'),
        fb_webhook_error=request.args.get('fb_webhook_error'),
    )


@bp.route('/settings/messaging/channels', methods=['POST'])
@login_required
@permission_required('edit_settings')
def messaging_create_channel():
    from app.services.messaging import channel_config_service as ccs
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Вкажіть назву'}), 400
    channel_type = data.get('channel_type') or 'telegram'
    if channel_type not in ('telegram', 'telegram_personal', 'viber'):
        return jsonify({'success': False, 'error': 'Непідтримуваний тип каналу'}), 400
    channel = ccs.create_channel(name, channel_type)
    return jsonify({'success': True, 'id': channel.id})


@bp.route('/settings/messaging/channels/<int:channel_id>', methods=['POST'])
@login_required
@permission_required('edit_settings')
def messaging_update_channel(channel_id):
    from app.models.messaging_channel import MessagingChannel
    from app.services.messaging import channel_config_service as ccs
    channel = MessagingChannel.query.get_or_404(channel_id)
    data = request.get_json() or {}
    ccs.update_channel(channel, name=data.get('name'), is_active=data.get('is_active'))
    if 'manager_ids' in data:
        ccs.set_managers(channel, [int(x) for x in data['manager_ids']])
    return jsonify({'success': True})


@bp.route('/settings/messaging/channels/<int:channel_id>/delete', methods=['POST'])
@login_required
@permission_required('edit_settings')
def messaging_delete_channel(channel_id):
    from app.models.messaging_channel import MessagingChannel
    from app.services.messaging import channel_config_service as ccs
    ccs.delete_channel(MessagingChannel.query.get_or_404(channel_id))
    return jsonify({'success': True})


@bp.route('/settings/messaging/channels/<int:channel_id>/webhook', methods=['POST'])
@login_required
@permission_required('edit_settings')
def messaging_register_webhook(channel_id):
    from app.models.messaging_channel import MessagingChannel
    from app.services.messaging import channel_config_service as ccs
    channel = MessagingChannel.query.get_or_404(channel_id)
    try:
        ccs.register_webhook(channel)
        return jsonify({'success': True, 'url': ccs.webhook_url(channel)})
    except Exception as exc:  # noqa: BLE001
        return jsonify({'success': False, 'error': str(exc)}), 400


@bp.route('/settings/messaging/facebook/start')
@login_required
@permission_required('edit_settings')
def messaging_facebook_start():
    """Kick off Facebook Login for Business — connects Instagram without any
    manual token copying (see app/services/messaging/facebook_oauth.py)."""
    from app.services.messaging import facebook_oauth
    state = secrets.token_urlsafe(24)
    session['fb_oauth_state'] = state
    try:
        return redirect(facebook_oauth.authorize_url(state))
    except RuntimeError as exc:
        current_app.logger.warning('Facebook OAuth not configured: %s', exc)
        return redirect(url_for('settings.messaging_page',
                                 fb_error='Facebook-підключення ще не готове, зверніться до розробника'))


@bp.route('/settings/messaging/facebook/callback')
@login_required
@permission_required('edit_settings')
def messaging_facebook_callback():
    from app.services.messaging import facebook_oauth, session_crypto

    error = request.args.get('error_description') or request.args.get('error')
    if error:
        return redirect(url_for('settings.messaging_page', fb_error=error))

    state = request.args.get('state')
    expected_state = session.pop('fb_oauth_state', None)
    if not state or not expected_state or state != expected_state:
        return redirect(url_for('settings.messaging_page', fb_error='Недійсний OAuth-стан, спробуйте ще раз'))

    code = request.args.get('code')
    if not code:
        return redirect(url_for('settings.messaging_page', fb_error='Facebook не повернув код авторизації'))

    try:
        short_token = facebook_oauth.exchange_code_for_user_token(code)
        long_token = facebook_oauth.exchange_long_lived_token(short_token)
        pages = facebook_oauth.list_connected_pages(long_token)
    except RuntimeError as exc:
        return redirect(url_for('settings.messaging_page', fb_error=str(exc)))

    if not pages:
        return redirect(url_for('settings.messaging_page',
                                 fb_error='Жодна зі сторінок не має підключеного Instagram Business акаунту'))

    # Encrypt each Page token now so it round-trips through the picker form
    # without ever sitting in the (unencrypted) session cookie.
    for p in pages:
        p['encrypted_token'] = session_crypto.encrypt(p.pop('page_access_token'))

    return render_template('settings/messaging_facebook_pages.html', pages=pages)


@bp.route('/settings/messaging/facebook/select-page', methods=['POST'])
@login_required
@permission_required('edit_settings')
def messaging_facebook_select_page():
    from app.services.messaging import channel_config_service as ccs

    page_id = request.form.get('page_id')
    page_name = request.form.get('page_name')
    ig_id = request.form.get('ig_id')
    ig_username = request.form.get('ig_username')
    encrypted_token = request.form.get('encrypted_token')
    if not (page_id and ig_id and encrypted_token):
        return redirect(url_for('settings.messaging_page', fb_error='Некоректні дані сторінки'))

    channel = ccs.create_instagram_channel_from_page(
        page_id=page_id, page_name=page_name or page_id,
        ig_id=ig_id, ig_username=ig_username or '',
        page_access_token_encrypted=encrypted_token,
    )
    try:
        ccs.register_webhook(channel)
        return redirect(url_for('settings.messaging_page', fb_success='1'))
    except Exception as exc:  # noqa: BLE001
        return redirect(url_for('settings.messaging_page', fb_success='1',
                                 fb_webhook_error=str(exc)))


@bp.route('/settings/messaging/whatsapp/complete', methods=['POST'])
@login_required
@permission_required('edit_settings')
def messaging_whatsapp_complete():
    """Finish WhatsApp Embedded Signup — called by JS after Meta's popup posts
    back {code, waba_id, phone_number_id} (see messaging.html)."""
    from app.services.messaging import facebook_oauth, session_crypto, channel_config_service as ccs

    data = request.get_json(silent=True) or {}
    code = data.get('code')
    waba_id = data.get('waba_id')
    phone_number_id = data.get('phone_number_id')
    if not (code and waba_id and phone_number_id):
        return jsonify({'success': False, 'error': 'Некоректні дані від Facebook'}), 400

    try:
        token = facebook_oauth.exchange_embedded_signup_code(code)
    except RuntimeError as exc:
        current_app.logger.warning('WhatsApp Embedded Signup token exchange failed: %s', exc)
        return jsonify({'success': False, 'error': 'Не вдалось підключити WhatsApp, зверніться до розробника'}), 400

    graph_root = f'https://graph.facebook.com/{current_app.config.get("INBOX_INSTAGRAM_GRAPH_VERSION") or "v23.0"}'

    display_phone_number = phone_number_id
    try:
        r = requests.get(f'{graph_root}/{phone_number_id}',
                          params={'fields': 'display_phone_number', 'access_token': token}, timeout=30)
        display_phone_number = r.json().get('display_phone_number') or phone_number_id
    except Exception:  # noqa: BLE001
        pass

    channel = ccs.create_whatsapp_channel_from_signup(
        waba_id=waba_id, phone_number_id=phone_number_id,
        display_phone_number=display_phone_number,
        access_token_encrypted=session_crypto.encrypt(token),
    )

    # A newly connected number must be registered with the Cloud API before it
    # can send/receive — a one-time call, PIN is only needed for re-registration.
    try:
        pin = f'{secrets.randbelow(1000000):06d}'
        requests.post(f'{graph_root}/{phone_number_id}/register',
                       headers={'Authorization': f'Bearer {token}'},
                       json={'messaging_product': 'whatsapp', 'pin': pin}, timeout=30)
        ccs.register_webhook(channel)
        return jsonify({'success': True})
    except Exception as exc:  # noqa: BLE001
        return jsonify({'success': True, 'warning': str(exc)})


@bp.route('/settings/messaging/channels/<int:channel_id>/telegram-personal/send-code', methods=['POST'])
@login_required
@permission_required('edit_settings')
def messaging_tg_personal_send_code(channel_id):
    from app.models.messaging_channel import MessagingChannel
    from app.services.messaging import telegram_personal_auth as auth
    channel = MessagingChannel.query.get_or_404(channel_id)
    phone = (request.get_json(silent=True) or {}).get('phone', '').strip()
    if not phone:
        return jsonify({'success': False, 'error': 'Вкажіть номер телефону'}), 400
    try:
        auth.request_code(channel, phone)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({'success': False, 'error': str(exc)}), 400


@bp.route('/settings/messaging/channels/<int:channel_id>/telegram-personal/confirm-code', methods=['POST'])
@login_required
@permission_required('edit_settings')
def messaging_tg_personal_confirm_code(channel_id):
    from app.models.messaging_channel import MessagingChannel
    from app.services.messaging import telegram_personal_auth as auth
    channel = MessagingChannel.query.get_or_404(channel_id)
    code = (request.get_json(silent=True) or {}).get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'error': 'Вкажіть код'}), 400
    try:
        auth.confirm_code(channel, code)
        db.session.commit()
        return jsonify({'success': True})
    except auth.NeedsPasswordError:
        return jsonify({'success': False, 'needs_password': True})
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({'success': False, 'error': str(exc)}), 400


@bp.route('/settings/messaging/channels/<int:channel_id>/telegram-personal/confirm-password', methods=['POST'])
@login_required
@permission_required('edit_settings')
def messaging_tg_personal_confirm_password(channel_id):
    from app.models.messaging_channel import MessagingChannel
    from app.services.messaging import telegram_personal_auth as auth
    channel = MessagingChannel.query.get_or_404(channel_id)
    password = (request.get_json(silent=True) or {}).get('password', '')
    if not password:
        return jsonify({'success': False, 'error': 'Вкажіть пароль'}), 400
    try:
        auth.confirm_password(channel, password)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({'success': False, 'error': str(exc)}), 400


@bp.route('/settings/charges')
@login_required
@permission_required('view_settings')
def charges_page():
    from app.services.billing_service import get_charges_data
    date_from = request.args.get('date_from', '').strip() or None
    date_to = request.args.get('date_to', '').strip() or None
    client_search = request.args.get('client_search', '').strip() or None
    page = int(request.args.get('page', 1) or 1)
    data = get_charges_data(date_from, date_to, client_search=client_search, page=page)
    return render_template(
        'settings/charges.html',
        rows=data['rows'],
        total_amount=data['total_amount'],
        count=data['count'],
        page=data['page'],
        pages=data['pages'],
        date_from=date_from or '',
        date_to=date_to or '',
        client_search=client_search or '',
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


@bp.route('/settings/payment_accounts', methods=['GET'])
def get_payment_accounts():
    items = Settings.query.filter_by(type='payment_account').order_by(Settings.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])

@bp.route('/settings/payment_accounts', methods=['POST'])
def add_payment_account():
    data = request.get_json()
    value = (data.get('value') or '').strip()
    if not value:
        return jsonify({'success': False, 'error': 'Назва не може бути порожньою'}), 400
    if Settings.query.filter_by(type='payment_account', value=value).first():
        return jsonify({'success': False, 'error': 'Такий рахунок вже існує'}), 400
    item = Settings(type='payment_account', value=value)
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
    if item.type == SETTING_EXPENSE_TYPE:
        # Перевіряти треба FK, а не legacy-рядок expense_type: саме expense_type_id
        # використовують звіти, і саме він тримає посилання на цей рядок. Стара
        # перевірка дивилась лише на текстову копію, тож тип, привʼязаний тільки
        # по FK, вважався невикористаним — і видалення падало вже на рівні БД.
        in_use = Transaction.query.filter(
            or_(
                Transaction.expense_type_id == item.id,
                Transaction.expense_type == item.value,
            )
        ).first()
        if in_use:
            return jsonify({'success': False, 'error': 'Тип витрати використовується в транзакціях і не може бути видалений'}), 400
    if item.type == SETTING_SIZE:
        # Прайси тепер захищені RESTRICT на рівні БД — повідомляємо зрозуміло,
        # замість того щоб віддавати IntegrityError у трасуванні.
        from app.models.price import Price
        if Price.query.filter_by(size_id=item.id).first():
            return jsonify({'success': False, 'error': 'Розмір використовується в прайсах і не може бути видалений'}), 400
    if item.type == SETTING_PAYMENT_ACCOUNT:
        linked = Transaction.query.filter(
            or_(
                Transaction.payment_account_id == item.id,
                Transaction.target_payment_account_id == item.id,
            )
        ).first()
        if linked:
            return jsonify({'success': False, 'error': 'Рахунок використовується в транзакціях і не може бути видалений'}), 400
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
            'phone': u.phone or '',
            'telegram_registered': u.telegram_registered,
            'telegram_username': u.telegram_username or '',
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
    phone_raw = (data.get('phone') or '').strip()
    phone = normalize_phone(phone_raw) if phone_raw else None

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
    if phone_raw and not phone:
        errors.append('Неправильний формат телефону')
    if phone and User.query.filter_by(phone=phone).first():
        errors.append('Користувач з таким телефоном вже існує')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    role = Role.query.filter_by(name=role_name).first()
    if not role:
        role = Role(name=role_name, description=role_name.capitalize())
        db.session.add(role)
        db.session.flush()

    email = f'{username}@crm.local'
    user = User(username=username, display_name=display_name, email=email, user_type=role_name,
                is_active=True, phone=phone)
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
        'phone': user.phone or '',
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
    phone_raw = (data.get('phone') or '').strip()
    phone = normalize_phone(phone_raw) if phone_raw else None

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
    if phone_raw and not phone:
        errors.append('Неправильний формат телефону')
    if phone and User.query.filter(User.phone == phone, User.id != user_id).first():
        errors.append('Користувач з таким телефоном вже існує')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    user.username = username
    user.display_name = display_name
    user.user_type = role_name
    user.phone = phone

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
        'phone': user.phone or '',
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


@bp.route('/settings/users/<int:user_id>/reset-telegram', methods=['POST'])
@login_required
@permission_required('manage_users')
def reset_user_telegram(user_id):
    user = User.query.get_or_404(user_id)
    user.telegram_chat_id = None
    user.telegram_username = None
    user.telegram_registered = False
    user.telegram_notifications_enabled = True
    user.last_telegram_activity = None
    db.session.commit()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Sale Options (florist pricing calculator)
# ---------------------------------------------------------------------------

@bp.route('/settings/sale_options', methods=['GET'])
@login_required
@permission_required('view_settings')
def get_sale_options():
    from app.models.sale_option import SaleOption
    items = SaleOption.query.order_by(SaleOption.sort_order.nullslast(), SaleOption.name).all()
    return jsonify([{
        'id': i.id,
        'name': i.name,
        'tiers_json': i.tiers_json,
        'is_active': i.is_active,
        'sort_order': i.sort_order,
        'icon_url': f'/settings/sale_option_icons/{i.icon_filename}' if i.icon_filename else None,
    } for i in items])


@bp.route('/settings/sale_options', methods=['POST'])
@login_required
@permission_required('edit_settings')
def add_sale_option():
    import json
    from app.models.sale_option import SaleOption
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Назва не може бути порожньою'}), 400
    tiers = data.get('tiers') or []
    if not tiers:
        return jsonify({'success': False, 'error': 'Потрібен хоча б один поріг'}), 400
    try:
        tiers_validated = [
            {'min_amount': float(t['min_amount']), 'coefficient': float(t['coefficient'])}
            for t in tiers
        ]
    except (KeyError, ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Невірний формат порогів'}), 400
    tiers_validated.sort(key=lambda t: t['min_amount'], reverse=True)
    if tiers_validated[-1]['min_amount'] != 0:
        return jsonify({'success': False, 'error': 'Потрібен дефолтний поріг із мінімальною сумою 0'}), 400
    item = SaleOption(
        name=name,
        tiers_json=json.dumps(tiers_validated),
        is_active=data.get('is_active', True),
        sort_order=data.get('sort_order'),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({'success': True, 'item': {
        'id': item.id, 'name': item.name,
        'tiers_json': item.tiers_json, 'is_active': item.is_active,
    }})


@bp.route('/settings/sale_options/<int:option_id>', methods=['PUT'])
@login_required
@permission_required('edit_settings')
def update_sale_option(option_id):
    import json
    from app.models.sale_option import SaleOption
    item = SaleOption.query.get_or_404(option_id)
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Назва не може бути порожньою'}), 400
    tiers = data.get('tiers') or []
    if not tiers:
        return jsonify({'success': False, 'error': 'Потрібен хоча б один поріг'}), 400
    try:
        tiers_validated = [
            {'min_amount': float(t['min_amount']), 'coefficient': float(t['coefficient'])}
            for t in tiers
        ]
    except (KeyError, ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Невірний формат порогів'}), 400
    tiers_validated.sort(key=lambda t: t['min_amount'], reverse=True)
    if tiers_validated[-1]['min_amount'] != 0:
        return jsonify({'success': False, 'error': 'Потрібен дефолтний поріг із мінімальною сумою 0'}), 400
    item.name = name
    item.tiers_json = json.dumps(tiers_validated)
    item.is_active = data.get('is_active', item.is_active)
    if 'sort_order' in data:
        item.sort_order = data['sort_order']
    db.session.commit()
    return jsonify({'success': True, 'item': {
        'id': item.id, 'name': item.name,
        'tiers_json': item.tiers_json, 'is_active': item.is_active,
    }})


@bp.route('/settings/sale_options/<int:option_id>', methods=['DELETE'])
@login_required
@permission_required('edit_settings')
def delete_sale_option(option_id):
    from app.models.sale_option import SaleOption
    item = SaleOption.query.get_or_404(option_id)
    _delete_icon_file(item.icon_filename)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True})


def _icon_folder():
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    folder = os.path.join(base, 'uploads', 'sale_option_icons')
    os.makedirs(folder, exist_ok=True)
    return folder


def _delete_icon_file(filename):
    if not filename:
        return
    try:
        path = os.path.join(_icon_folder(), filename)
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


_ALLOWED_ICON_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif', 'svg'}


@bp.route('/settings/sale_options/<int:option_id>/icon', methods=['POST'])
@login_required
@permission_required('edit_settings')
def upload_sale_option_icon(option_id):
    from app.models.sale_option import SaleOption
    item = SaleOption.query.get_or_404(option_id)
    file = request.files.get('icon')
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'Файл не вибрано'}), 400
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in _ALLOWED_ICON_EXTENSIONS:
        return jsonify({'success': False, 'error': 'Недозволений формат. Дозволено: jpg, png, webp, svg'}), 400
    _delete_icon_file(item.icon_filename)
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(_icon_folder(), filename))
    item.icon_filename = filename
    db.session.commit()
    return jsonify({'success': True, 'icon_url': f'/settings/sale_option_icons/{filename}'})


@bp.route('/settings/sale_options/<int:option_id>/icon', methods=['DELETE'])
@login_required
@permission_required('edit_settings')
def delete_sale_option_icon(option_id):
    from app.models.sale_option import SaleOption
    item = SaleOption.query.get_or_404(option_id)
    _delete_icon_file(item.icon_filename)
    item.icon_filename = None
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/settings/sale_option_icons/<path:filename>')
def serve_sale_option_icon(filename):
    folder = _icon_folder()
    return send_from_directory(folder, filename)
