from flask import render_template, request, jsonify
from datetime import datetime, date
import logging

from . import distribution_bp
from app.models.delivery import Delivery
from app.models.courier import Courier
from app.models.client import Client

from app.extensions import db

logger = logging.getLogger(__name__)

@distribution_bp.route('/distribution', methods=['GET'])
def distribution_page():
    """Сторінка розподілу доставок між кур'єрами"""
    
    # Отримуємо дату з параметрів або беремо сьогоднішню
    date_str = request.args.get('date', date.today().isoformat())
    
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = date.today()
    
    # Отримуємо доставки на вибрану дату зі статусом "Очікує" або "Розподілено"
    # Виключаємо самовивіз (is_pickup=True), бо його не потрібно розподіляти
    deliveries = Delivery.query.join(Client).filter(
        Delivery.delivery_date == selected_date,
        Delivery.status.in_(['Очікує', 'Розподілено']),
        Delivery.is_pickup == False  # Тільки доставки, не самовивіз
    ).order_by(
        Delivery.time_from.asc().nullslast(),
        Delivery.id.asc()
    ).all()
    
    # Отримуємо всіх активних кур'єрів (не на паузі)
    couriers = Courier.query.filter_by(active=True).all()
    active_courier_ids = {courier.id for courier in couriers}
    
    # Групуємо доставки за кур'єрами
    courier_groups = {}
    unassigned_deliveries = []
    
    for delivery in deliveries:
        if delivery.courier_id and delivery.courier_id in active_courier_ids:
            # Доставка призначена активному кур'єру
            if delivery.courier_id not in courier_groups:
                courier_groups[delivery.courier_id] = []
            courier_groups[delivery.courier_id].append(delivery)
        else:
            # Доставка не призначена або призначена неактивному кур'єру
            unassigned_deliveries.append(delivery)
    
    logger.info(f'Distribution page: {len(deliveries)} deliveries on {selected_date}')
    
    return render_template(
        'distribution.html',
        deliveries=deliveries,
        unassigned_deliveries=unassigned_deliveries,
        courier_groups=courier_groups,
        couriers=couriers,
        selected_date=selected_date
    )

@distribution_bp.route('/distribution/assign', methods=['POST'])
def assign_deliveries():
    """Призначити доставки кур'єру"""
    
    data = request.get_json()
    courier_id = data.get('courier_id')
    delivery_ids = data.get('delivery_ids', [])
    
    if not courier_id or not delivery_ids:
        return jsonify({'success': False, 'error': 'Missing courier_id or delivery_ids'}), 400
    
    try:
        # Перевіряємо чи існує кур'єр
        courier = Courier.query.get(courier_id)
        if not courier:
            return jsonify({'success': False, 'error': 'Courier not found'}), 404
        
        # Призначаємо доставки кур'єру
        updated_count = 0
        for delivery_id in delivery_ids:
            delivery = Delivery.query.get(delivery_id)
            if delivery and delivery.status in ['Очікує', 'Розподілено']:
                delivery.courier_id = courier_id
                delivery.status = 'Розподілено'
                updated_count += 1
        
        db.session.commit()
        
        logger.info(f'Assigned {updated_count} deliveries to courier {courier_id}')
        
        return jsonify({
            'success': True,
            'message': f'Призначено {updated_count} доставок кур\'єру {courier.name}',
            'updated_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error assigning deliveries: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@distribution_bp.route('/distribution/unassign', methods=['POST'])
def unassign_deliveries():
    """Зняти призначення доставок з кур'єра"""
    
    data = request.get_json()
    delivery_ids = data.get('delivery_ids', [])
    
    if not delivery_ids:
        return jsonify({'success': False, 'error': 'Missing delivery_ids'}), 400
    
    try:
        updated_count = 0
        for delivery_id in delivery_ids:
            delivery = Delivery.query.get(delivery_id)
            if delivery and delivery.status == 'Розподілено':
                delivery.courier_id = None
                delivery.status = 'Очікує'
                updated_count += 1
        
        db.session.commit()
        
        logger.info(f'Unassigned {updated_count} deliveries')
        
        return jsonify({
            'success': True,
            'message': f'Знято призначення з {updated_count} доставок',
            'updated_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error unassigning deliveries: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500 