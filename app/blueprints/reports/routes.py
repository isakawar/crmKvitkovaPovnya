from flask import Blueprint, render_template
from app.services.reports_service import get_reports_data

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports')
def reports_page():
    data = get_reports_data()
    return render_template('reports.html', **data) 