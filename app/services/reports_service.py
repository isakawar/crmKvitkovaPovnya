from app.models import Courier, Delivery, Order
from datetime import datetime, timedelta
from app.extensions import db

def get_reports_data():
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # --- Кур'єри: скільки доставок зробив кожен за тиждень/місяць (по delivered_at) ---
    couriers = Courier.query.all()
    courier_stats = []
    for c in couriers:
        week_count = Delivery.query.filter(
            Delivery.courier_id == c.id,
            Delivery.status == 'Доставлено',
            Delivery.delivered_at != None,
            Delivery.delivered_at >= week_ago
        ).count()
        month_count = Delivery.query.filter(
            Delivery.courier_id == c.id,
            Delivery.status == 'Доставлено',
            Delivery.delivered_at != None,
            Delivery.delivered_at >= month_ago
        ).count()
        courier_stats.append({
            'name': c.name,
            'week': week_count,
            'month': month_count,
            'total': c.deliveries_count or 0
        })

    # --- Нові замовлення за тиждень/місяць (по created_at) ---
    week_orders = Order.query.filter(Order.created_at >= week_ago).count()
    month_orders = Order.query.filter(Order.created_at >= month_ago).count()

    # --- Всього доставок за тиждень/місяць (по delivered_at) ---
    week_deliveries = Delivery.query.filter(Delivery.delivered_at != None, Delivery.delivered_at >= week_ago).count()
    month_deliveries = Delivery.query.filter(Delivery.delivered_at != None, Delivery.delivered_at >= month_ago).count()

    # --- Додатково: зміна статусу за тиждень/місяць (по status_changed_at) ---
    week_status_changes = Delivery.query.filter(Delivery.status_changed_at != None, Delivery.status_changed_at >= week_ago).count()
    month_status_changes = Delivery.query.filter(Delivery.status_changed_at != None, Delivery.status_changed_at >= month_ago).count()

    return {
        'courier_stats': courier_stats,
        'orders_stats': {
            'week': week_orders,
            'month': month_orders
        },
        'deliveries_stats': {
            'week': week_deliveries,
            'month': month_deliveries
        },
        'status_changes_stats': {
            'week': week_status_changes,
            'month': month_status_changes
        }
    } 