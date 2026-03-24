from flask import jsonify, render_template, request
from flask_login import login_required
from sqlalchemy.orm import joinedload

from app.blueprints.subscriptions import subscriptions_bp
from app.extensions import db
from app.models import Order, Delivery, Client
from app.models.subscription import Subscription
from app.models.settings import Settings
from app.services.subscription_service import (
    get_subscriptions,
    extend_subscription,
    delete_subscription,
)
import logging

logger = logging.getLogger(__name__)


def _format_address(street='', building_number='', floor='', entrance='', address_comment=''):
    parts = []
    line = ' '.join(p for p in [street, building_number] if p)
    if line:
        parts.append(line)
    if floor:
        parts.append(f'поверх {floor}')
    if entrance:
        parts.append(f'підʼїзд {entrance}')
    if address_comment:
        parts.append(address_comment)
    return ', '.join(p for p in parts if p)


@subscriptions_bp.route('/subscriptions', methods=['GET'])
@login_required
def subscriptions_list():
    search_query = request.args.get('q', '').strip()
    city_filter = request.args.get('city', '').strip()
    type_filter = request.args.get('type', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 30

    subscriptions = get_subscriptions(
        q=search_query or None,
        city=city_filter or None,
        sub_type=type_filter or None,
    )

    data = []
    for sub in subscriptions:
        all_deliveries = [d for order in sub.orders for d in order.deliveries]
        total = len(all_deliveries)
        completed = sum(1 for d in all_deliveries if d.status == 'Доставлено')
        data.append({'subscription': sub, 'total': total, 'completed': completed})

    active_count = sum(1 for s in data if s['completed'] < s['total'])
    completed_count = sum(1 for s in data if s['total'] > 0 and s['completed'] >= s['total'])
    total_count = len(data)

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    data_page = data[start_idx:end_idx]

    cities = Settings.query.filter_by(type='city').order_by(Settings.value).all()
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()

    return render_template(
        'subscriptions/list.html',
        subscriptions=data_page,
        active_count=active_count,
        completed_count=completed_count,
        total_count=total_count,
        per_page=per_page,
        page=page,
        cities=cities,
        search_query=search_query,
        city_filter=city_filter,
        type_filter=type_filter,
        delivery_types=delivery_types,
        sizes=sizes,
        for_whom=for_whom,
        marketing_sources=[],
    )


@subscriptions_bp.route('/subscriptions/<int:subscription_id>', methods=['GET'])
@login_required
def subscription_detail(subscription_id):
    subscription = (
        Subscription.query
        .options(
            joinedload(Subscription.client),
            joinedload(Subscription.orders).joinedload(Order.deliveries),
        )
        .get_or_404(subscription_id)
    )

    all_deliveries = sorted(
        [d for order in subscription.orders for d in order.deliveries],
        key=lambda d: (d.delivery_date, d.id)
    )
    total_deliveries = len(all_deliveries)
    completed_deliveries = sum(1 for d in all_deliveries if d.status == 'Доставлено')
    next_delivery = next((d for d in all_deliveries if d.status in ['Очікує', 'Розподілено']), None)
    final_delivery = all_deliveries[-1] if all_deliveries else None

    # First order date = subscription start
    first_order = min(subscription.orders, key=lambda o: o.delivery_date, default=None)

    # Build "related orders" — show each order as a cycle row
    orders_sorted = sorted(subscription.orders, key=lambda o: o.delivery_date)
    related_orders = []
    for order in orders_sorted:
        order_deliveries = sorted(order.deliveries, key=lambda d: d.delivery_date)
        completed_count = sum(1 for d in order_deliveries if d.status == 'Доставлено')
        related_orders.append({
            'id': order.id,
            'is_current': order == orders_sorted[-1],
            'created_at': order.created_at.strftime('%d.%m.%Y %H:%M') if order.created_at else '',
            'first_delivery_date': order.delivery_date.strftime('%d.%m.%Y') if order.delivery_date else '',
            'delivery_type': subscription.type,
            'size': subscription.size,
            'city': subscription.city,
            'is_extended': False,
            'recipient_name': subscription.recipient_name,
            'deliveries_total': len(order_deliveries),
            'deliveries_completed': completed_count,
            'sequence_number': order.sequence_number,
        })

    return jsonify({
        'id': subscription.id,
        'client': {
            'instagram': subscription.client.instagram if subscription.client else '',
            'phone': subscription.client.phone if subscription.client else '',
            'telegram': subscription.client.telegram if subscription.client else '',
        },
        'recipient': {
            'name': subscription.recipient_name,
            'phone': subscription.recipient_phone,
            'social': subscription.recipient_social or '',
        },
        'delivery': {
            'city': subscription.city,
            'address': 'Самовивіз' if subscription.is_pickup else _format_address(
                subscription.street,
                subscription.building_number,
                subscription.floor,
                subscription.entrance,
                subscription.address_comment,
            ),
            'delivery_type': subscription.type,
            'size': subscription.size,
            'custom_amount': subscription.custom_amount,
            'delivery_day': subscription.delivery_day,
            'first_delivery_date': first_order.delivery_date.strftime('%d.%m.%Y') if first_order else '',
            'time_from': subscription.time_from or '',
            'time_to': subscription.time_to or '',
            'delivery_method': subscription.delivery_method or 'courier',
            'is_pickup': subscription.is_pickup,
            'for_whom': subscription.for_whom or '',
        },
        'notes': {
            'comment': subscription.comment or '',
            'preferences': subscription.preferences or '',
            'address_comment': subscription.address_comment or '',
            'bouquet_type': subscription.bouquet_type or '',
            'composition_type': subscription.composition_type or '',
        },
        'stats': {
            'total_deliveries': total_deliveries,
            'completed_deliveries': completed_deliveries,
            'active_deliveries': max(total_deliveries - completed_deliveries, 0),
            'can_extend': not subscription.is_extended,
            'is_extended': bool(subscription.is_extended),
            'next_delivery_date': next_delivery.delivery_date.strftime('%d.%m.%Y') if next_delivery else '',
            'final_delivery_date': final_delivery.delivery_date.strftime('%d.%m.%Y') if final_delivery else '',
        },
        'deliveries': [
            {
                'id': d.id,
                'delivery_date': d.delivery_date.strftime('%d.%m.%Y') if d.delivery_date else '',
                'status': d.status,
                'time_from': d.time_from or '',
                'time_to': d.time_to or '',
                'address': 'Самовивіз' if d.is_pickup else _format_address(
                    d.street or subscription.street,
                    d.building_number or subscription.building_number,
                    d.floor or subscription.floor,
                    d.entrance or subscription.entrance,
                    d.address_comment or subscription.address_comment,
                ),
                'phone': d.phone or subscription.recipient_phone or '',
                'comment': d.comment or '',
                'preferences': d.preferences or subscription.preferences or '',
                'delivery_method': d.delivery_method or subscription.delivery_method or 'courier',
                'is_subscription': True,
            }
            for d in all_deliveries
        ],
        'related_orders': related_orders,
    })


@subscriptions_bp.route('/subscriptions/<int:subscription_id>/extend', methods=['POST'])
@login_required
def subscription_extend(subscription_id):
    subscription = Subscription.query.get_or_404(subscription_id)
    if subscription.is_extended:
        return jsonify({'success': False, 'error': 'Цю підписку вже продовжено'}), 400
    try:
        extend_subscription(subscription)
        return jsonify({
            'success': True,
            'message': f'Підписку продовжено для клієнта {subscription.client.instagram}',
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error extending subscription {subscription_id}: {e}')
        return jsonify({'success': False, 'error': 'Помилка при продовженні підписки'}), 500


@subscriptions_bp.route('/subscriptions/<int:subscription_id>/delete', methods=['POST'])
@login_required
def subscription_delete(subscription_id):
    subscription = Subscription.query.get_or_404(subscription_id)
    try:
        delete_subscription(subscription)
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting subscription {subscription_id}: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
