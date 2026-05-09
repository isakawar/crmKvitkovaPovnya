from flask import Blueprint, render_template, request
from flask_login import login_required

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
