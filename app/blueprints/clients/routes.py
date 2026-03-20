from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app.extensions import db
from app.services.client_service import get_all_clients, create_client, get_clients_json, get_client_by_id, update_client
from app.models.settings import Settings
from app.models.order import Order

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/clients', methods=['GET'])
def clients_list():
    page = int(request.args.get('page', 1))
    per_page = 28
    search_query = request.args.get('q', '').strip()
    sub_filter = request.args.get('sub', '')

    all_clients = get_all_clients()

    active_sub_client_ids = set(
        row[0] for row in db.session.query(Order.client_id)
        .filter(Order.delivery_type.in_(['Weekly', 'Monthly', 'Bi-weekly']))
        .distinct().all()
    )

    if search_query:
        q = search_query.lower()
        all_clients = [
            c for c in all_clients
            if (c.instagram and q in c.instagram.lower())
            or (c.telegram and q in c.telegram.lower())
            or (c.phone and q in c.phone)
        ]

    if sub_filter == 'active':
        all_clients = [c for c in all_clients if c.id in active_sub_client_ids]
    elif sub_filter == 'inactive':
        all_clients = [c for c in all_clients if c.id not in active_sub_client_ids]

    total_clients = len(all_clients)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    clients_on_page = all_clients[start_idx:end_idx]

    has_next = end_idx < total_clients
    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1

    marketing_sources = Settings.query.filter_by(type='marketing_source').order_by(Settings.value).all()

    return render_template('clients/list.html',
                         clients=clients_on_page,
                         page=page,
                         prev_page=prev_page,
                         next_page=next_page,
                         has_next=has_next,
                         clients_count=total_clients,
                         marketing_sources=marketing_sources,
                         active_sub_client_ids=active_sub_client_ids,
                         search_query=search_query,
                         sub_filter=sub_filter)

@clients_bp.route('/clients/new', methods=['POST'])
def client_create():
    instagram = request.form.get('instagram', '').strip()
    phone = request.form.get('phone', '').strip()
    telegram = request.form.get('telegram', '').strip() or None
    credits_raw = request.form.get('credits', 0)
    try:
        credits = int(credits_raw) if str(credits_raw).strip() else 0
    except ValueError:
        credits = 0
    marketing_source = request.form.get('marketing_source', '').strip()
    personal_discount = request.form.get('personal_discount', '').strip()
    personal_discount = int(personal_discount) if personal_discount.isdigit() else None
    client, error = create_client(
        instagram=instagram,
        phone=phone,
        telegram=telegram,
        credits=credits,
        marketing_source=marketing_source,
        personal_discount=personal_discount
    )
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
        'instagram': client.instagram,
        'phone': client.phone,
        'telegram': client.telegram or '',
        'credits': client.credits,
        'marketing_source': client.marketing_source,
        'personal_discount': client.personal_discount or ''
    })

@clients_bp.route('/clients/<int:client_id>', methods=['POST'])
def client_update(client_id):
    instagram = request.form.get('instagram', '').strip()
    phone = request.form.get('phone', '').strip()
    telegram = request.form.get('telegram', '').strip() or None
    credits_raw = request.form.get('credits', 0)
    try:
        credits = int(credits_raw) if str(credits_raw).strip() else 0
    except ValueError:
        credits = 0
    marketing_source = request.form.get('marketing_source', '').strip()
    personal_discount = request.form.get('personal_discount', '').strip()
    personal_discount = int(personal_discount) if personal_discount.isdigit() else None
    client, error = update_client(
        client_id=client_id,
        instagram=instagram,
        phone=phone,
        telegram=telegram,
        credits=credits,
        marketing_source=marketing_source,
        personal_discount=personal_discount
    )
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
    client = Client.query.get_or_404(client_id)
    has_deliveries = Delivery.query.filter_by(client_id=client_id).first() is not None
    if has_deliveries:
        return jsonify({'success': False, 'error': 'Неможливо видалити клієнта з існуючими доставками'}), 400
    db.session.delete(client)
    db.session.commit()
    return jsonify({'success': True})

@clients_bp.route('/clients/json', methods=['GET'])
def clients_json():
    return jsonify(get_clients_json())

 
