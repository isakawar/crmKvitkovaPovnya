from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app.services.csv_import_service import preview_import, execute_import

import_csv_bp = Blueprint('import_csv', __name__, url_prefix='/import')


@import_csv_bp.route('/', methods=['GET'])
@login_required
def import_page():
    return render_template('import_csv/index.html')


@import_csv_bp.route('/preview', methods=['POST'])
@login_required
def preview():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не завантажено'}), 400
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Потрібен файл формату .csv'}), 400

    rows, error = preview_import(file.stream)
    if error:
        return jsonify({'error': error}), 400

    new_count = sum(1 for r in rows if r['client_status'] == 'new')
    existing_count = sum(1 for r in rows if r['client_status'] == 'exists')
    warning_count = sum(1 for r in rows if r['warnings'])

    return jsonify({
        'rows': rows,
        'summary': {
            'total': len(rows),
            'new_clients': new_count,
            'existing_clients': existing_count,
            'warnings': warning_count,
        }
    })


@import_csv_bp.route('/execute', methods=['POST'])
@login_required
def execute():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Немає даних'}), 400

    rows = data.get('rows', [])
    first_delivery_date = data.get('first_delivery_date', '')
    delivery_day = data.get('delivery_day', 'ПН')

    if not rows:
        return jsonify({'error': 'Немає рядків для імпорту'}), 400
    if not first_delivery_date:
        return jsonify({'error': 'Вкажіть дату першої доставки'}), 400

    result = execute_import(rows, first_delivery_date, delivery_day)
    return jsonify(result)
