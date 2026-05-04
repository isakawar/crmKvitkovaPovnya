from flask import Blueprint, render_template, request
from flask_login import login_required
from app.services.reports_service import (
    get_reports_data,
    get_florist_sales_data,
    get_deliveries_analytics,
    get_pl_data,
    get_subscription_renewal_rate,
)
from app.utils.decorators import permission_required

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports')
@login_required
@permission_required('view_reports')
def reports_page():
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    active_tab = request.args.get('tab', 'deliveries')

    selected_month = date_from[:7] if date_from else ''

    data = get_reports_data(selected_month)
    data.update(get_florist_sales_data(selected_month))
    data.update(get_deliveries_analytics(date_from or None, date_to or None))
    data.update(get_pl_data(date_from or None, date_to or None))
    data.update(get_subscription_renewal_rate(date_from or None, date_to or None))
    data['date_from'] = date_from
    data['date_to'] = date_to
    data['active_tab'] = active_tab
    return render_template('reports/index.html', **data)
