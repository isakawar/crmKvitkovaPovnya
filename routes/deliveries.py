from flask import Blueprint, render_template, request, jsonify
from models import db, Delivery, Order, Client
import datetime

deliveries_bp = Blueprint('deliveries', __name__)

@deliveries_bp.route('/deliveries', methods=['GET'])
def deliveries_list():
    deliveries = Delivery.query.order_by(Delivery.id.desc()).all()
    return render_template('deliveries_list.html', deliveries=deliveries)

@deliveries_bp.route('/deliveries/<int:delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    d = Delivery.query.get_or_404(delivery_id)
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
    d = Delivery.query.get_or_404(delivery_id)
    data = request.json or {}
    if 'delivery_date' in data:
        d.delivery_date = datetime.datetime.strptime(data['delivery_date'], '%Y-%m-%d').date()
    if 'time_window' in data:
        d.time_window = data['time_window']
    if 'time_from' in data:
        d.time_from = data['time_from']
    if 'time_to' in data:
        d.time_to = data['time_to']
    if 'street' in data:
        d.street = data['street']
    if 'building_number' in data:
        d.building_number = data['building_number']
    if 'phone' in data:
        d.phone = data['phone']
    if 'comment' in data:
        d.comment = data['comment']
    db.session.commit()
    return jsonify({'success': True})

@deliveries_bp.route('/deliveries/<int:delivery_id>/status', methods=['POST'])
def set_delivery_status(delivery_id):
    d = Delivery.query.get_or_404(delivery_id)
    data = request.json
    new_status = data.get('status', 'Доставлено')
    d.status = new_status
    db.session.commit()
    return jsonify({'success': True, 'status': d.status}) 