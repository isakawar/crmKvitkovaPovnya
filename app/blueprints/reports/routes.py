from datetime import date as date_type
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models.client import Client
from app.models.transaction import Transaction
from app.services.reports_service import (
    get_orders_data,
    get_deliveries_analytics,
    get_pl_data,
    get_subscription_renewal_rate,
    get_florist_sales_data,
    get_cash_flow_data,
    get_active_months,
    get_client_revenue_breakdown,
)
from app.utils.decorators import permission_required

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/reports')
@login_required
@permission_required('view_reports')
def reports_page():
    date_from = request.args.get('date_from', '').strip() or None
    date_to = request.args.get('date_to', '').strip() or None
    active_tab = request.args.get('tab', 'deliveries')

    return render_template(
        'reports/index.html',
        orders=get_orders_data(date_from, date_to),
        deliveries=get_deliveries_analytics(date_from, date_to),
        pl=get_pl_data(date_from, date_to),
        subscriptions=get_subscription_renewal_rate(date_from, date_to),
        florist=get_florist_sales_data(date_from, date_to),
        cash_flow=get_cash_flow_data(date_from, date_to),
        revenue=get_client_revenue_breakdown(date_from, date_to),
        active_tab=active_tab,
        date_from=date_from or '',
        date_to=date_to or '',
        active_months=get_active_months(),
    )


@reports_bp.route('/reports/revenue/adjust', methods=['POST'])
@login_required
@permission_required('view_reports')
def revenue_adjust():
    data = request.get_json(silent=True) or {}
    adjustments = data.get('adjustments', [])
    if not adjustments:
        return jsonify({'ok': False, 'error': 'no adjustments'}), 400

    for item in adjustments:
        try:
            client_id = int(item['client_id'])
            sub_id = int(item['subscription_id']) if item.get('subscription_id') else None
            month = date_type.fromisoformat(item['month'])
            delta_charged = int(item.get('delta_charged', 0))
            delta_paid = int(item.get('delta_paid', 0))
        except (KeyError, ValueError, TypeError):
            return jsonify({'ok': False, 'error': 'invalid item'}), 400

        if delta_charged == 0 and delta_paid == 0:
            continue

        client = db.session.get(Client, client_id)
        if client is None:
            return jsonify({'ok': False, 'error': f'client {client_id} not found'}), 400

        month_label = month.strftime('%m.%Y')

        if delta_charged != 0:
            db.session.add(Transaction(
                transaction_type='delivery_charge',
                client_id=client_id,
                amount=delta_charged,
                delivery_id=None,
                date=month,
                comment=f'Адмін коригування балансу за {month_label}',
                created_by_id=current_user.id,
            ))
            client.credits = (client.credits or 0) - delta_charged

        if delta_paid != 0:
            db.session.add(Transaction(
                transaction_type='credit',
                client_id=client_id,
                amount=delta_paid,
                date=month,
                comment=f'Адмін коригування балансу за {month_label}',
                created_by_id=current_user.id,
            ))
            client.credits = (client.credits or 0) + delta_paid

    db.session.commit()
    return jsonify({'ok': True})
