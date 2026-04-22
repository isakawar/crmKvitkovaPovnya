from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app.extensions import db
from app.services.client_service import get_all_clients, create_client, get_clients_json, get_client_by_id, update_client, search_clients
from app.models.settings import Settings
from app.models.subscription import Subscription

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/clients', methods=['GET'])
def clients_list():
    page = int(request.args.get('page', 1))
    per_page = 28
    search_query = request.args.get('q', '').strip()
    sub_filter = request.args.get('sub', '')

    pagination = search_clients(q=search_query or None, sub_filter=sub_filter or None, page=page, per_page=per_page)
    clients_on_page = pagination.items

    # Підвантажуємо dot-індикатори тільки для клієнтів поточної сторінки
    client_ids_on_page = [c.id for c in clients_on_page]
    if client_ids_on_page:
        active_sub_client_ids = set(
            row[0] for row in db.session.query(Subscription.client_id)
            .filter(Subscription.client_id.in_(client_ids_on_page))
            .distinct().all()
        )
    else:
        active_sub_client_ids = set()

    marketing_sources = Settings.query.filter_by(type='marketing_source').order_by(Settings.value).all()

    return render_template('clients/list.html',
                         clients=clients_on_page,
                         page=pagination.page,
                         prev_page=pagination.page - 1 if pagination.page > 1 else 1,
                         next_page=pagination.page + 1,
                         has_next=pagination.has_next,
                         clients_count=pagination.total,
                         marketing_sources=marketing_sources,
                         active_sub_client_ids=active_sub_client_ids,
                         search_query=search_query,
                         sub_filter=sub_filter)

def _parse_client_form(form):
    credits_raw = form.get('credits', 0)
    try:
        credits = int(credits_raw) if str(credits_raw).strip() else 0
    except ValueError:
        credits = 0
    personal_discount_raw = form.get('personal_discount', '').strip()
    personal_discount = int(personal_discount_raw) if personal_discount_raw.isdigit() else None
    return {
        'instagram': form.get('instagram', '').strip() or None,
        'telegram': form.get('telegram', '').strip() or None,
        'phone': form.get('phone', '').strip() or None,
        'name': form.get('name', '').strip() or None,
        'phone_viber': form.get('phone_viber') == 'on',
        'phone_telegram': form.get('phone_telegram') == 'on',
        'phone_whatsapp': form.get('phone_whatsapp') == 'on',
        'credits': credits,
        'marketing_source': form.get('marketing_source', '').strip() or None,
        'personal_discount': personal_discount,
        'email': form.get('email', '').strip() or None,
    }


@clients_bp.route('/clients/new', methods=['POST'])
def client_create():
    kwargs = _parse_client_form(request.form)
    client, error = create_client(**kwargs)
    if error:
        if isinstance(error, dict):
            payload = {'success': False}
            payload.update(error)
            return jsonify(payload), 400
        return jsonify({'success': False, 'error': error}), 400
    return jsonify({'success': True})

@clients_bp.route('/clients/<int:client_id>', methods=['GET'])
def get_client(client_id):
    client = get_client_by_id(client_id)
    return jsonify({
        'id': client.id,
        'name': client.name or '',
        'instagram': client.instagram or '',
        'telegram': client.telegram or '',
        'phone': client.phone or '',
        'phone_viber': client.phone_viber,
        'phone_telegram': client.phone_telegram,
        'phone_whatsapp': client.phone_whatsapp,
        'credits': client.credits,
        'marketing_source': client.marketing_source or '',
        'personal_discount': client.personal_discount or '',
        'email': client.email or '',
        'created_at': client.created_at.strftime('%d.%m.%Y') if client.created_at else None,
    })

@clients_bp.route('/clients/<int:client_id>', methods=['POST'])
def client_update(client_id):
    kwargs = _parse_client_form(request.form)
    client, error = update_client(client_id=client_id, **kwargs)
    if error:
        if isinstance(error, dict):
            payload = {'success': False}
            payload.update(error)
            return jsonify(payload), 400
        return jsonify({'success': False, 'error': error}), 400
    return jsonify({'success': True})

@clients_bp.route('/clients/<int:client_id>/delete', methods=['POST'])
def client_delete(client_id):
    from app.models.client import Client
    from app.models.delivery import Delivery
    from sqlalchemy.exc import IntegrityError
    client = Client.query.get_or_404(client_id)
    has_subscriptions = Subscription.query.filter_by(client_id=client_id).first() is not None
    if has_subscriptions:
        return jsonify({'success': False, 'error': 'Неможливо видалити клієнта з активною підпискою'}), 400
    has_deliveries = Delivery.query.filter_by(client_id=client_id).first() is not None
    if has_deliveries:
        return jsonify({'success': False, 'error': 'Неможливо видалити клієнта з існуючими доставками'}), 400
    try:
        db.session.delete(client)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Неможливо видалити клієнта: є пов\'язані замовлення або записи'}), 400
    return jsonify({'success': True})

@clients_bp.route('/clients/json', methods=['GET'])
def clients_json():
    return jsonify(get_clients_json())

 
