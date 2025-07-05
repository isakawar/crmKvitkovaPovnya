from flask import Blueprint, render_template, request, jsonify
from app.models.settings import Settings
from app.extensions import db

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
def settings():
    return render_template('settings.html')

@settings_bp.route('/settings/cities', methods=['GET'])
def get_cities():
    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    return jsonify([{'id': c.id, 'value': c.value} for c in cities])

@settings_bp.route('/settings/cities', methods=['POST'])
def add_city():
    data = request.get_json()
    value = (data.get('value') or '').strip()
    if not value:
        return jsonify({'success': False, 'error': 'Назва міста не може бути порожньою'}), 400
    if Settings.query.filter_by(type='city', value=value).first():
        return jsonify({'success': False, 'error': 'Таке місто вже існує'}), 400
    city = Settings(type='city', value=value)
    db.session.add(city)
    db.session.commit()
    return jsonify({'success': True, 'city': {'id': city.id, 'value': city.value}})

@settings_bp.route('/settings/delivery_types', methods=['GET'])
def get_delivery_types():
    items = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])

@settings_bp.route('/settings/delivery_types', methods=['POST'])
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

@settings_bp.route('/settings/sizes', methods=['GET'])
def get_sizes():
    items = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])

@settings_bp.route('/settings/sizes', methods=['POST'])
def add_size():
    data = request.get_json()
    value = (data.get('value') or '').strip()
    if not value:
        return jsonify({'success': False, 'error': 'Назва не може бути порожньою'}), 400
    if Settings.query.filter_by(type='size', value=value).first():
        return jsonify({'success': False, 'error': 'Такий розмір вже існує'}), 400
    item = Settings(type='size', value=value)
    db.session.add(item)
    db.session.commit()
    return jsonify({'success': True, 'item': {'id': item.id, 'value': item.value}})

@settings_bp.route('/settings/for_whom', methods=['GET'])
def get_for_whom():
    items = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])

@settings_bp.route('/settings/for_whom', methods=['POST'])
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