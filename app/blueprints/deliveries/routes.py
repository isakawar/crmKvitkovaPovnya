from flask import Blueprint, render_template, request, jsonify
from app.services.delivery_service import get_deliveries, get_delivery_by_id, update_delivery, set_delivery_status, assign_deliveries, get_all_deliveries_ordered, get_all_couriers, assign_courier_to_deliveries
from app.models import Delivery
from app.extensions import db
from datetime import datetime

deliveries_bp = Blueprint('deliveries', __name__)

@deliveries_bp.route('/deliveries', methods=['GET'])
def deliveries_list():
    date_str = request.args.get('date')
    client_instagram = request.args.get('client_instagram', '').strip()
    recipient_phone = request.args.get('recipient_phone', '').strip()
    client_phone = request.args.get('client_phone', '').strip()  # для сумісності, але не використовується
    financial_week = request.args.get('financial_week')
    page = int(request.args.get('page', 1))
    per_page = 30
    
    # Конвертуємо financial_week в число якщо він є
    if financial_week:
        try:
            financial_week = int(financial_week)
        except ValueError:
            financial_week = None
    
    deliveries, selected_date = get_deliveries(date_str, client_instagram, recipient_phone, financial_week)
    couriers = get_all_couriers()
    
    # Проста пагінація
    total_deliveries = len(deliveries)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    deliveries_on_page = deliveries[start_idx:end_idx]
    
    has_next = end_idx < total_deliveries
    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1
    
    return render_template('deliveries_list.html', 
                         deliveries=deliveries_on_page, 
                         selected_date=selected_date, 
                         couriers=couriers,
                         page=page,
                         prev_page=prev_page,
                         next_page=next_page,
                         has_next=has_next,
                         deliveries_count=total_deliveries)

@deliveries_bp.route('/deliveries/<int:delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    d = get_delivery_by_id(delivery_id)
    order = d.order if hasattr(d, 'order') else None
    return jsonify({
        'id': d.id,
        'city': order.city if order else '',
        'street': d.street or (order.street if order else ''),
        'building_number': d.building_number or (order.building_number if order else ''),
        'phone': d.phone or '',
        'time_from': d.time_from or '',
        'time_to': d.time_to or '',
        'delivery_date': d.delivery_date.strftime('%Y-%m-%d'),
        'comment': d.comment or '',
        'status': d.status,
        'size': d.size or (order.size if order else ''),
        'is_pickup': d.is_pickup,
        'is_subscription': d.is_subscription,
        'delivery_type': d.delivery_type,
        'client_instagram': d.client.instagram if d.client else '',
        'client_id': d.client_id
    })

@deliveries_bp.route('/deliveries/<int:delivery_id>/edit', methods=['POST'])
def edit_delivery(delivery_id):
    d = get_delivery_by_id(delivery_id)
    data = request.json or {}
    update_delivery(d, data)
    return jsonify({'success': True})

@deliveries_bp.route('/deliveries/<int:delivery_id>/status', methods=['POST'])
def set_status(delivery_id):
    d = get_delivery_by_id(delivery_id)
    data = request.json
    new_status = data.get('status', 'Доставлено')
    set_delivery_status(d, new_status)
    return jsonify({'success': True, 'status': d.status})

@deliveries_bp.route('/assign-deliveries', methods=['GET'])
def assign_deliveries_page():
    all_deliveries = get_all_deliveries_ordered()
    couriers = get_all_couriers()
    return render_template('assign_deliveries.html', all_deliveries=all_deliveries, couriers=couriers)

@deliveries_bp.route('/assign-deliveries', methods=['POST'])
def assign_deliveries_save():
    data = request.get_json()
    assign_deliveries(data)
    return jsonify({'success': True})

@deliveries_bp.route('/deliveries/assign-courier', methods=['POST'])
def assign_courier():
    data = request.get_json()
    delivery_ids = data.get('delivery_ids', [])
    courier_id = data.get('courier_id')
    if not delivery_ids or not courier_id:
        return jsonify({'success': False, 'error': 'Не вибрано доставки або курʼєра!'}), 400
    ok, error = assign_courier_to_deliveries(delivery_ids, courier_id)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': error}), 400

@deliveries_bp.route('/deliveries/<int:delivery_id>/future-deliveries', methods=['GET'])
def get_future_deliveries(delivery_id):
    """Отримати наступні доставки того ж замовлення"""
    d = get_delivery_by_id(delivery_id)
    if not d or not d.order_id:
        return jsonify([])
    
    # Отримуємо всі майбутні доставки цього замовлення (включаючи поточну)
    from datetime import datetime
    future_deliveries = Delivery.query.filter(
        Delivery.order_id == d.order_id,
        Delivery.delivery_date >= d.delivery_date,
        Delivery.id != d.id  # Виключаємо поточну доставку
    ).order_by(Delivery.delivery_date).all()
    
    return jsonify([{
        'id': fd.id,
        'delivery_date': fd.delivery_date.strftime('%Y-%m-%d'),
        'status': fd.status,
        'delivery_type': fd.delivery_type
    } for fd in future_deliveries])

@deliveries_bp.route('/deliveries/<int:delivery_id>/change-dates', methods=['POST'])
def change_delivery_dates(delivery_id):
    """Змінити дати доставок того ж замовлення"""
    data = request.get_json()
    changed_dates = data.get('changed_dates', {})
    
    if not changed_dates:
        return jsonify({'success': False, 'error': 'Немає дат для зміни'}), 400
    
    # Отримуємо поточну доставку для перевірки order_id
    current_delivery = Delivery.query.get(delivery_id)
    if not current_delivery:
        return jsonify({'success': False, 'error': 'Доставка не знайдена'}), 404
    
    try:
        for delivery_id_str, new_date_str in changed_dates.items():
            delivery_id_int = int(delivery_id_str)
            delivery = Delivery.query.get(delivery_id_int)
            
            # Перевіряємо, що доставка належить тому ж замовленню
            if delivery and delivery.order_id == current_delivery.order_id:
                new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
                delivery.delivery_date = new_date
            else:
                return jsonify({'success': False, 'error': 'Спроба змінити доставку з іншого замовлення'}), 403
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400 