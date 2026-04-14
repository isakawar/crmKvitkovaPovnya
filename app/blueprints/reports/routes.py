from flask import Blueprint, render_template, request
from flask_login import login_required
from app.services.reports_service import get_reports_data
from app.utils.decorators import permission_required

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports')
@login_required
@permission_required('view_reports')
def reports_page():
    selected_month = (request.args.get('month') or '').strip()
    data = get_reports_data(selected_month)
    return render_template('reports/index.html', **data)
