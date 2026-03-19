from flask import Blueprint, render_template, request
from flask_login import login_required
from app.services.reports_service import get_reports_data

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports')
@login_required
def reports_page():
    selected_month = (request.args.get('month') or '').strip()
    data = get_reports_data(selected_month)
    return render_template('reports/index.html', **data)
