from flask import Blueprint, render_template, request, jsonify
from app.services.delivery_service import get_deliveries, get_delivery_by_id, update_delivery, set_delivery_status, assign_deliveries, get_all_deliveries_ordered, get_all_couriers, assign_courier_to_deliveries
from app.models import Delivery, Settings, Order
from app.extensions import db
from datetime import datetime
import logging

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
    
    # Отримуємо дані з налаштувань для форми
    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()
    
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
                         deliveries_count=total_deliveries,
                         cities=cities,
                         delivery_types=delivery_types,
                         sizes=sizes,
                         for_whom=for_whom)

@deliveries_bp.route('/deliveries/<int:delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    d = get_delivery_by_id(delivery_id)
    order = d.order if hasattr(d, 'order') else None
    return jsonify({
        'id': d.id,
        'city': order.city if order else '',
        'street': d.street or (order.street if order else ''),
        'phone': d.phone or '',
        'time_from': d.time_from or '',
        'time_to': d.time_to or '',
        'delivery_date': d.delivery_date.strftime('%Y-%m-%d'),
        'size': d.size or (order.size if order else ''),
        'delivery_type': d.delivery_type or (order.delivery_type if order else ''),
        'status': d.status,
        'is_pickup': d.is_pickup,
        'is_subscription': d.is_subscription,
        'comment': d.comment or '',
        'preferences': d.preferences or '',
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
    data = request.get_json() or {}
    assign_deliveries(data)
    return jsonify({'success': True})

@deliveries_bp.route('/deliveries/assign-courier', methods=['POST'])
def assign_courier():
    data = request.get_json() or {}
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
    data = request.get_json() or {}
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

@deliveries_bp.route('/deliveries/<int:delivery_id>/extend-subscription', methods=['POST'])
def extend_delivery_subscription(delivery_id):
    """Продовжити підписку для доставки"""
    d = get_delivery_by_id(delivery_id)
    
    # Перевіряємо, чи це неоплачена доставка підписки
    if d.status != 'Не оплачена' or d.delivery_type not in ['Weekly', 'Monthly', 'Bi-weekly']:
        return jsonify({'success': False, 'error': 'Це не неоплачена доставка підписки'}), 400
    
    # Знаходимо замовлення цієї доставки
    order = d.order if hasattr(d, 'order') else None
    if not order:
        return jsonify({'success': False, 'error': 'Не знайдено замовлення для доставки'}), 404
    
    try:
        # Використовуємо ту ж логіку, що й для замовлень
        from app.services.order_service import WEEKDAY_MAP
        import datetime
        import calendar
        
        # Клонуємо замовлення
        new_order = Order(
            client_id=order.client_id,
            recipient_name=order.recipient_name,
            recipient_phone=order.recipient_phone,
            recipient_social=order.recipient_social,
            city=order.city,
            street=order.street,
            building_number=order.building_number,
            floor=order.floor,
            entrance=order.entrance,
            is_pickup=order.is_pickup,
            delivery_type=order.delivery_type,
            size=order.size,
            custom_amount=order.custom_amount,
            first_delivery_date=order.first_delivery_date,
            delivery_day=order.delivery_day,
            time_from=order.time_from,
            time_to=order.time_to,
            comment=order.comment,
            preferences=order.preferences,
            for_whom=order.for_whom,
            bouquet_size=order.bouquet_size,
            price_at_order=order.price_at_order,
            periodicity=order.periodicity,
            preferred_days=order.preferred_days
        )
        db.session.add(new_order)
        db.session.flush()  # Щоб отримати new_order.id

        # Переносимо поточну доставку до нового замовлення
        d.status = 'Очікує'
        d.is_subscription = True
        d.order_id = new_order.id
        
        # Відмічаємо старий order як продовжений
        order.is_subscription_extended = True
        
        # Створюємо 4 нові доставки
        prev_date = d.delivery_date
        desired_weekday = WEEKDAY_MAP.get(order.delivery_day, 0)
        deliveries = []
        
        for i in range(4):
            if order.delivery_type == 'Weekly':
                next_date = prev_date + datetime.timedelta(days=1)
                while next_date.weekday() != desired_weekday:
                    next_date += datetime.timedelta(days=1)
            elif order.delivery_type == 'Bi-weekly':
                next_date = prev_date + datetime.timedelta(days=8)
                while next_date.weekday() != desired_weekday:
                    next_date += datetime.timedelta(days=1)
            elif order.delivery_type == 'Monthly':
                year = prev_date.year + (prev_date.month // 12)
                month = (prev_date.month % 12) + 1
                c = calendar.Calendar()
                month_days = [d for d in c.itermonthdates(year, month) if d.month == month and d.weekday() == desired_weekday]
                next_date = None
                for d in month_days:
                    if d > prev_date:
                        next_date = d
                        break
                if not next_date:
                    next_date = prev_date + datetime.timedelta(days=30)
            else:
                next_date = prev_date + datetime.timedelta(weeks=1)
            deliveries.append(next_date)
            prev_date = next_date
        
        for i, d_date in enumerate(deliveries):
            is_subscription = i < 3
            status = 'Очікує' if is_subscription else 'Не оплачена'
            delivery = Delivery(
                order_id=new_order.id,
                client_id=order.client_id,
                delivery_date=d_date,
                status=status,
                comment=order.comment if i == 0 else None,
                preferences=order.preferences,
                street=order.street if not order.is_pickup else None,
                building_number=order.building_number if not order.is_pickup else None,
                time_from=order.time_from,
                time_to=order.time_to,
                size=order.size,
                phone=order.recipient_phone,
                is_pickup=order.is_pickup,
                delivery_type=order.delivery_type,
                is_subscription=is_subscription
            )
            db.session.add(delivery)
        db.session.commit()
        return jsonify({'success': True, 'message': f'Підписку продовжено для клієнта {order.client.instagram}'})
    except Exception as e:
        db.session.rollback()
        logging.error(f'Помилка продовження підписки доставки: {e}')
        return jsonify({'success': False, 'error': 'Помилка при продовженні підписки'}), 500