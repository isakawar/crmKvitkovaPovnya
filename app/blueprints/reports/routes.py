from datetime import date as date_type
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models.client import Client
from app.models.revenue_adjustment import RevenueAdjustment
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
    get_wedding_analytics,
    get_ltv_data,
    get_dashboard_kpis,
    get_subscription_record_card,
)
from app.utils.decorators import permission_required

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/reports')
@login_required
@permission_required('view_reports')
def reports_page():
    date_from = request.args.get('date_from', '').strip() or None
    date_to = request.args.get('date_to', '').strip() or None

    # v2 tabs: overview | sales | clients | balance. Map legacy tab names.
    _legacy_tab_map = {
        'deliveries': 'sales', 'pl': 'overview', 'cash_flow': 'overview',
        'export': 'overview', 'revenue': 'balance', 'wedding_ltv': 'clients',
    }
    active_tab = request.args.get('tab', 'overview')
    active_tab = _legacy_tab_map.get(active_tab, active_tab)
    if active_tab not in ('overview', 'sales', 'clients', 'balance'):
        active_tab = 'overview'

    pl = get_pl_data(date_from, date_to)

    return render_template(
        'reports/index.html',
        kpis=get_dashboard_kpis(date_from, date_to, pl=pl),
        orders=get_orders_data(date_from, date_to),
        deliveries=get_deliveries_analytics(date_from, date_to),
        pl=pl,
        subscriptions=get_subscription_renewal_rate(date_from, date_to),
        florist=get_florist_sales_data(date_from, date_to),
        cash_flow=get_cash_flow_data(date_from, date_to),
        revenue=get_client_revenue_breakdown(date_from, date_to),
        wedding=get_wedding_analytics(date_from, date_to),
        ltv=get_ltv_data(date_from, date_to),
        active_tab=active_tab,
        date_from=date_from or '',
        date_to=date_to or '',
        active_months=get_active_months(),
    )


@reports_bp.route('/reports/subscription/<int:subscription_id>/record-card')
@login_required
@permission_required('view_reports')
def subscription_record_card(subscription_id):
    card = get_subscription_record_card(subscription_id)
    if not card:
        return jsonify({'ok': False, 'error': 'not found'}), 404
    return jsonify({'ok': True, 'card': card})


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

        if delta_charged != 0:
            client = db.session.get(Client, client_id)
            if client is None:
                return jsonify({'ok': False, 'error': f'client {client_id} not found'}), 400
            tx = Transaction(
                transaction_type='delivery_charge',
                client_id=client_id,
                amount=delta_charged,
                delivery_id=None,
                date=month,
                comment=f'Ручне коригування нарахувань за {month.strftime("%m.%Y")}',
                created_by_id=current_user.id,
            )
            db.session.add(tx)
            client.credits = (client.credits or 0) - delta_charged

        if delta_paid != 0:
            q = db.session.query(RevenueAdjustment).filter(
                RevenueAdjustment.client_id == client_id,
                RevenueAdjustment.month == month,
            )
            if sub_id is None:
                q = q.filter(RevenueAdjustment.subscription_id.is_(None))
            else:
                q = q.filter(RevenueAdjustment.subscription_id == sub_id)

            adj = q.first()
            if adj:
                adj.adj_paid += delta_paid
            else:
                adj = RevenueAdjustment(
                    client_id=client_id,
                    subscription_id=sub_id,
                    month=month,
                    adj_charged=0,
                    adj_paid=delta_paid,
                )
                db.session.add(adj)

    db.session.commit()
    return jsonify({'ok': True})


@reports_bp.route('/reports/revenue/balance-adjust', methods=['POST'])
@login_required
@permission_required('view_reports')
def revenue_balance_adjust():
    data = request.get_json(silent=True) or {}
    adjustments = data.get('adjustments', [])
    if not adjustments:
        return jsonify({'ok': False, 'error': 'no adjustments'}), 400

    for item in adjustments:
        try:
            client_id = int(item['client_id'])
            month = date_type.fromisoformat(item['month'])
            delta = int(item['delta'])
        except (KeyError, ValueError, TypeError):
            return jsonify({'ok': False, 'error': 'invalid item'}), 400

        if delta == 0:
            continue

        client = db.session.get(Client, client_id)
        if client is None:
            return jsonify({'ok': False, 'error': f'client {client_id} not found'}), 400

        existing = (
            db.session.query(Transaction)
            .filter(
                Transaction.transaction_type == 'adjustment',
                Transaction.client_id == client_id,
                Transaction.date == month,
            )
            .first()
        )

        if existing:
            new_amount = existing.amount + delta
            if new_amount == 0:
                db.session.delete(existing)
            else:
                existing.amount = new_amount
                existing.comment = f'Коригування балансу {month.strftime("%m.%Y")}'
        else:
            tx = Transaction(
                transaction_type='adjustment',
                client_id=client_id,
                amount=delta,
                date=month,
                comment=f'Коригування балансу {month.strftime("%m.%Y")}',
                created_by_id=current_user.id,
            )
            db.session.add(tx)

        client.credits = (client.credits or 0) + delta

    db.session.commit()
    return jsonify({'ok': True})
