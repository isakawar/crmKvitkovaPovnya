from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app.extensions import db
from app.services.client_service import get_all_clients, create_client, get_clients_json
from app.services.courier_service import get_all_couriers, create_courier

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/clients', methods=['GET'])
def clients_list():
    clients = get_all_clients()
    return render_template('clients_list.html', clients=clients)

@clients_bp.route('/clients/new', methods=['POST'])
def client_create():
    phone = request.form['phone']
    instagram = request.form['instagram']
    telegram = request.form['telegram']
    credits = int(request.form.get('credits', 0))
    city = request.form.get('city', '')
    client, error = create_client(phone, instagram, telegram, credits, city)
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