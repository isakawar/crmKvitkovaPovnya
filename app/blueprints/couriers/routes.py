from flask import render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime, date, timedelta
import logging
from sqlalchemy import func, extract

from . import couriers_bp
from app.models.courier import Courier
from app.models.delivery import Delivery
from app.services.courier_service import get_all_couriers, create_courier
from app.extensions import db

logger = logging.getLogger(__name__)

@couriers_bp.route('/couriers', methods=['GET'])
def couriers_list():
    """Сторінка списку кур'єрів з статистикою"""
    
    # Отримуємо період для статистики
    period = request.args.get('period', 'month')  # week, month, year, all
    
    # Обчислюємо дати для періоду
    today = date.today()
    if period == 'week':
        start_date = today - timedelta(days=7)
        period_title = "за тиждень"
    elif period == 'month':
        start_date = today - timedelta(days=30)
        period_title = "за місяць"
    elif period == 'year':
        start_date = today - timedelta(days=365)
        period_title = "за рік"
    else:  # all
        start_date = None
        period_title = "за весь час"
    
    # Отримуємо всіх кур'єрів
    couriers = Courier.query.order_by(Courier.name).all()
    
    # Статистика для кожного кур'єра
    courier_stats = []
    for courier in couriers:
        deliveries_query = Delivery.query.filter(
            Delivery.courier_id == courier.id,
            Delivery.is_pickup == False
        )

        if start_date:
            deliveries_query = deliveries_query.filter(Delivery.delivery_date >= start_date)

        total_deliveries = deliveries_query.count()
        completed = deliveries_query.filter(Delivery.status == 'Доставлено').count()
        in_progress = deliveries_query.filter(Delivery.status == 'Розподілено').count()

        last_delivery = deliveries_query.filter(
            Delivery.status == 'Доставлено'
        ).order_by(Delivery.delivered_at.desc()).first()

        courier_stats.append({
            'courier': courier,
            'total_deliveries': total_deliveries,
            'completed': completed,
            'in_progress': in_progress,
            'last_delivery': last_delivery,
        })
    
    # Сортуємо за кількістю доставок
    courier_stats.sort(key=lambda x: x['total_deliveries'], reverse=True)
    
    # Загальна статистика
    active_couriers = [c for c in couriers if c.active]

    total_stats = {
        'total_couriers': len(couriers),
        'active_couriers': len(active_couriers),
        'total_deliveries': sum(cs['total_deliveries'] for cs in courier_stats),
        'completed_deliveries': sum(cs['completed'] for cs in courier_stats),
    }
    
    logger.info(f'Couriers page: {len(couriers)} couriers, period: {period}')
    
    return render_template(
        'couriers_list.html',
        courier_stats=courier_stats,
        total_stats=total_stats,
        period=period,
        period_title=period_title
    )

@couriers_bp.route('/couriers/new', methods=['POST'])
def create_new_courier():
    """Створити нового кур'єра"""
    
    data = request.get_json() if request.is_json else request.form
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()

    if not name or not phone:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Ім\'я та телефон обов\'язкові'}), 400
        flash('Ім\'я та телефон обов\'язкові', 'error')
        return redirect(url_for('couriers.couriers_list'))
    
    try:
        # Перевіряємо чи не існує кур'єр з таким телефоном
        existing_courier = Courier.query.filter_by(phone=phone).first()
        if existing_courier:
            if request.is_json:
                return jsonify({'success': False, 'error': 'Кур\'єр з таким телефоном вже існує'}), 400
            flash('Кур\'єр з таким телефоном вже існує', 'error')
            return redirect(url_for('couriers.couriers_list'))
        
        courier = create_courier(name, phone)
        
        logger.info(f'Created new courier: {courier.name} ({courier.phone})')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': f'Кур\'єра {courier.name} успішно створено',
                'courier': {
                    'id': courier.id,
                    'name': courier.name,
                    'phone': courier.phone,
                    'active': courier.active
                }
            })
        
        flash(f'Кур\'єра {courier.name} успішно створено', 'success')
        return redirect(url_for('couriers.couriers_list'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error creating courier: {str(e)}')
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        flash('Помилка створення кур\'єра', 'error')
        return redirect(url_for('couriers.couriers_list'))

@couriers_bp.route('/couriers/<int:courier_id>/toggle', methods=['POST'])
def toggle_courier_status(courier_id):
    """Змінити статус активності кур'єра"""
    
    courier = Courier.query.get_or_404(courier_id)
    
    try:
        courier.active = not courier.active
        db.session.commit()
        
        status = "активовано" if courier.active else "деактивовано"
        logger.info(f'Courier {courier.name} {status}')
        
        return jsonify({
            'success': True,
            'message': f'Кур\'єра {courier.name} {status}',
            'active': courier.active
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error toggling courier status: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@couriers_bp.route('/couriers/<int:courier_id>/delete', methods=['POST'])
def delete_courier(courier_id):
    """Видалити кур'єра"""
    
    courier = Courier.query.get_or_404(courier_id)
    
    try:
        # Перевіряємо чи є активні доставки
        active_deliveries = Delivery.query.filter(
            Delivery.courier_id == courier_id,
            Delivery.status.in_(['Очікує', 'Розподілено'])
        ).count()
        
        if active_deliveries > 0:
            return jsonify({
                'success': False, 
                'error': f'Неможливо видалити кур\'єра - у нього є {active_deliveries} активних доставок'
            }), 400
        
        courier_name = courier.name
        db.session.delete(courier)
        db.session.commit()
        
        logger.info(f'Deleted courier: {courier_name}')
        
        return jsonify({
            'success': True,
            'message': f'Кур\'єра {courier_name} успішно видалено'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting courier: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@couriers_bp.route('/couriers/<int:courier_id>/edit', methods=['POST'])
def edit_courier(courier_id):
    """Редагувати кур'єра"""
    
    courier = Courier.query.get_or_404(courier_id)
    data = request.get_json()

    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()

    if not name or not phone:
        return jsonify({'success': False, 'error': 'Ім\'я та телефон обов\'язкові'}), 400
    
    try:
        # Перевіряємо чи не існує інший кур'єр з таким телефоном
        existing_courier = Courier.query.filter(
            Courier.phone == phone,
            Courier.id != courier_id
        ).first()
        
        if existing_courier:
            return jsonify({'success': False, 'error': 'Кур\'єр з таким телефоном вже існує'}), 400
        
        courier.name = name
        courier.phone = phone
        db.session.commit()
        
        logger.info(f'Updated courier: {courier.name} ({courier.phone})')
        
        return jsonify({
            'success': True,
            'message': f'Дані кур\'єра {courier.name} оновлено',
            'courier': {
                'id': courier.id,
                'name': courier.name,
                'phone': courier.phone,
                'active': courier.active
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error updating courier: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@couriers_bp.route('/couriers/<int:courier_id>/reset-telegram', methods=['POST'])
def reset_courier_telegram(courier_id):
    """Скинути Telegram прив'язку кур'єра"""
    
    try:
        courier = Courier.query.get_or_404(courier_id)
        
        # Зберігаємо дані для логування
        had_telegram = courier.telegram_registered
        telegram_username = courier.telegram_username
        
        # Скидаємо всі Telegram поля
        courier.telegram_chat_id = None
        courier.telegram_username = None
        courier.telegram_registered = False
        courier.telegram_notifications_enabled = True  # Увімкнуто по дефолту для наступної реєстрації
        courier.last_telegram_activity = None
        
        db.session.commit()
        
        if had_telegram:
            logger.info(f'Reset Telegram binding for courier {courier.name} (ID: {courier.id}, username: {telegram_username})')
            message = f'Telegram прив\'язку кур\'єра {courier.name} скинуто. Тепер він може зареєструватися знову.'
        else:
            logger.info(f'Attempted to reset Telegram for courier {courier.name} (ID: {courier.id}) - was not linked')
            message = f'Кур\'єр {courier.name} не був прив\'язаний до Telegram.'
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error resetting Telegram for courier {courier_id}: {str(e)}')
        return jsonify({'success': False, 'error': 'Помилка скидання Telegram прив\'язки'}), 500 