from flask import Blueprint, render_template, request, jsonify
from app.services.delivery_service import get_deliveries, get_delivery_by_id, update_delivery, set_delivery_status, assign_deliveries, get_all_deliveries_ordered, get_all_couriers, assign_courier_to_deliveries

deliveries_bp = Blueprint('deliveries', __name__)

@deliveries_bp.route('/deliveries', methods=['GET'])
def deliveries_list():
    date_str = request.args.get('date')
    client_phone = request.args.get('client_phone', '').strip()
    deliveries, selected_date = get_deliveries(date_str, client_phone)
    couriers = get_all_couriers()
    return render_template('deliveries_list.html', deliveries=deliveries, selected_date=selected_date, couriers=couriers)

@deliveries_bp.route('/deliveries/<int:delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    d = get_delivery_by_id(delivery_id)
    return jsonify({
        'id': d.id,
        'client': d.client.instagram,
        'city': d.client.city,
        'street': d.order.street,
        'building_number': d.order.building_number,
        'phone': d.phone,
        'comment': d.comment,
        'time_window': d.order.time_window,
        'delivery_date': d.delivery_date.strftime('%Y-%m-%d'),
        'status': d.status,
        'size': d.order.size,
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