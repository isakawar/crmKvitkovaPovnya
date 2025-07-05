from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app.extensions import db
from app.services.client_service import get_all_clients, create_client, get_clients_json, get_client_by_id, update_client
from app.services.courier_service import get_all_couriers, create_courier
from app.models.settings import Settings

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/clients', methods=['GET'])
def clients_list():
    page = int(request.args.get('page', 1))
    per_page = 30
    all_clients = get_all_clients()
    
    # Проста пагінація
    total_clients = len(all_clients)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    clients_on_page = all_clients[start_idx:end_idx]
    
    has_next = end_idx < total_clients
    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1
    
    marketing_sources = Settings.query.filter_by(type='marketing_source').order_by(Settings.value).all()
    
    return render_template('clients_list.html', 
                         clients=clients_on_page, 
                         page=page, 
                         prev_page=prev_page, 
                         next_page=next_page, 
                         has_next=has_next, 
                         clients_count=total_clients,
                         marketing_sources=marketing_sources)

@clients_bp.route('/clients/new', methods=['POST'])
def client_create():
    instagram = request.form.get('instagram', '').strip()
    phone = request.form.get('phone', '').strip()
    telegram = request.form.get('telegram', '').strip() or None
    credits = int(request.form.get('credits', 0))
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
    credits = int(request.form.get('credits', 0))
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
        return jsonify({'success': False, 'error': error}), 400
    return jsonify({'success': True})

@clients_bp.route('/clients/json', methods=['GET'])
def clients_json():
    return jsonify(get_clients_json())

# --- Courier CRUD ---
@clients_bp.route('/couriers', methods=['GET', 'POST'])
def couriers_list():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        create_courier(name, phone)
        return redirect(url_for('clients.couriers_list'))
    couriers = get_all_couriers()
    return render_template('couriers_list.html', couriers=couriers) 