from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app.models import Settings, Price
from app.models.courier import Courier
from app.extensions import db
from app.utils.decorators import permission_required

bp = Blueprint('settings', __name__)

@bp.route('/settings')
@login_required
@permission_required('view_settings')
def settings_page():
    settings = Settings.query.first()
    couriers = Courier.query.order_by(Courier.name).all()
    active_couriers = [c for c in couriers if c.active]
    telegram_couriers = [c for c in couriers if c.telegram_registered]
    courier_stats = {
        'total': len(couriers),
        'active': len(active_couriers),
        'telegram': len(telegram_couriers),
    }
    return render_template(
        'settings/index.html',
        settings=settings,
        couriers=couriers,
        courier_stats=courier_stats
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

@bp.route('/settings/cities', methods=['GET'])
def get_cities():
    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    return jsonify([{'id': c.id, 'value': c.value} for c in cities])

@bp.route('/settings/cities', methods=['POST'])
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
    items = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])

@bp.route('/settings/sizes', methods=['POST'])
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


@bp.route('/settings/<int:item_id>', methods=['DELETE'])
@login_required
@permission_required('edit_settings')
def delete_setting(item_id):
    item = Settings.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/settings/prices', methods=['GET'])
def get_prices():
    sub_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    prices = Price.query.all()
    price_map = {(p.subscription_type_id, p.size_id): p.price for p in prices}
    return jsonify({
        'subscription_types': [{'id': s.id, 'value': s.value} for s in sub_types],
        'sizes': [{'id': s.id, 'value': s.value} for s in sizes],
        'prices': {f'{k[0]}_{k[1]}': v for k, v in price_map.items()},
    })


@bp.route('/settings/prices', methods=['POST'])
def save_prices():
    data = request.get_json()
    # data: { "sub_id_size_id": price_value, ... }
    for key, value in data.items():
        parts = key.split('_')
        if len(parts) != 2:
            continue
        try:
            sub_id = int(parts[0])
            size_id = int(parts[1])
            price_val = int(value)
        except (ValueError, TypeError):
            continue
        existing = Price.query.filter_by(subscription_type_id=sub_id, size_id=size_id).first()
        if existing:
            existing.price = price_val
        else:
            db.session.add(Price(subscription_type_id=sub_id, size_id=size_id, price=price_val))
    db.session.commit()
    return jsonify({'success': True}) 
