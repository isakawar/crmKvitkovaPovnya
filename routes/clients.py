from flask import Blueprint, render_template, request, jsonify
from models import db, Client

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/clients', methods=['GET'])
def clients_list():
    clients = Client.query.order_by(Client.id.desc()).all()
    return render_template('clients_list.html', clients=clients)

@clients_bp.route('/clients/new', methods=['POST'])
def client_create():
    phone = request.form['phone']
    instagram = request.form['instagram']
    telegram = request.form['telegram']
    credits = int(request.form.get('credits', 0))
    city = request.form.get('city', '')
    if not city:
        return jsonify({'success': False, 'error': 'Місто є обовʼязковим!'}), 400
    # Перевірка унікальності телефону
    if Client.query.filter_by(phone=phone).first():
        return jsonify({'success': False, 'error': 'Клієнт з таким номером вже існує!'}), 400
    client = Client(phone=phone, instagram=instagram, telegram=telegram, credits=credits, city=city)
    db.session.add(client)
    db.session.commit()
    return jsonify({'success': True})

@clients_bp.route('/clients/json', methods=['GET'])
def clients_json():
    clients = Client.query.order_by(Client.id.desc()).all()
    return jsonify([
        {'id': c.id, 'phone': c.phone, 'instagram': c.instagram, 'city': c.city} for c in clients
    ]) 